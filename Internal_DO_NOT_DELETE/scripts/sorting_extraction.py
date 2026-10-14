from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import zlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sorting_document_profile import build_document_profile
from sorting_extraction_fields import enrich_text_from_fields, extract_fields
from sorting_extraction_gate import decide_ocr_gate
import sorting_ocr_gate
import sorting_platform as platform_support

try:
    import fitz  # type: ignore
except Exception:
    fitz = None


OPENXML_TEXT_CHAR_LIMIT = 200_000
OPENXML_XML_BYTES_LIMIT = 1_000_000
OPENXML_SHARED_STRINGS_BYTES_LIMIT = 2_500_000
OPENXML_WORKSHEETS_LIMIT = 12


def _log_extraction(message: str) -> None:
    if os.environ.get("SORTING_TRACE_EXTRACTION") != "1":
        return
    print(f"[extract] {message}", flush=True)


@dataclass
class ExtractionRuntime:
    text_cache: dict[Path, str]
    manual_review_heavy_ocr_paths: set[Path]
    command_exists_cache: dict[str, bool]
    ocr_binary_candidates: list[Path]
    swift_pdf_splitter: Path
    cache_root: Path
    text_cache_version: str
    informative_text_patterns: list[str]
    normalize_text: Callable[[str], str]

def _run_command(args: list[str], timeout: int = 20) -> str:
    try:
        completed = subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout)
    except FileNotFoundError:
        return ""
    except subprocess.TimeoutExpired:
        _log_extraction(f"{Path(args[0]).name}: timeout after {timeout}s")
        return ""
    if completed.returncode != 0:
        _log_extraction(f"{Path(args[0]).name}: exit {completed.returncode}: {completed.stderr[:200].strip()}")
        return ""
    return completed.stdout


def run_command(args: list[str], timeout: int = 20) -> str:
    return _run_command(args, timeout=timeout)


def heavy_ocr_enabled() -> bool:
    return os.environ.get("SORTING_ALLOW_HEAVY_OCR") == "1"


def text_cache_path(path: Path, *, runtime: ExtractionRuntime) -> Path:
    try:
        stat = path.stat()
        payload = (
            f"{runtime.text_cache_version}|"
            f"heavy_ocr={int(heavy_ocr_enabled())}|"
            f"ocr={available_ocr_binary(runtime=runtime) or ''}|"
            f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime_ns)}"
        )
    except Exception:
        payload = f"{runtime.text_cache_version}|heavy_ocr={int(heavy_ocr_enabled())}|{path.resolve()}"
    digest = hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()
    return runtime.cache_root / f"{digest}.txt"


def load_disk_cached_text(path: Path, *, runtime: ExtractionRuntime) -> str | None:
    cache_path = text_cache_path(path, runtime=runtime)
    try:
        if not cache_path.exists() or not cache_path.is_file():
            return None
        text = cache_path.read_text(encoding="utf-8")
        return text if text.strip() else None
    except Exception:
        return None


def save_disk_cached_text(path: Path, text: str, *, runtime: ExtractionRuntime) -> None:
    if not text.strip():
        return
    cache_path = text_cache_path(path, runtime=runtime)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(cache_path)
    except Exception:
        return


def normalize_extracted_text(text: str) -> str:
    if not text:
        return ""
    lines = [repair_ocr_line(line.strip()) for line in text.replace("\r", "\n").splitlines()]
    compact = [line for line in lines if line]
    return "\n".join(compact)


def repair_ocr_line(line: str) -> str:
    if not line:
        return ""
    replacements = {
        "CЧET": "СЧЕТ",
        "CЧ": "СЧ",
        "AO ": "АО ",
        "OOO ": "ООО ",
        "OOO ": "ООО ",
        "PЕЗ.": "РЕЗ.",
        "PЕЗ ": "РЕЗ ",
        "HДФЛ": "НДФЛ",
        "PУБ": "РУБ",
    }
    for old, new in replacements.items():
        line = line.replace(old, new)
    def repair_token(match: re.Match[str]) -> str:
        token = match.group(0)
        cyrillic_count = sum(1 for ch in token if "А" <= ch <= "я" or ch in {"Ё", "ё"})
        latin_count = sum(1 for ch in token if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
        if not cyrillic_count or not latin_count:
            return token
        if token[:1] and ("А" <= token[0] <= "я" or token[0] in {"Ё", "ё"}):
            return "".join(_latin_to_cyrillic(ch) for ch in token)
        if cyrillic_count >= latin_count:
            return "".join(_latin_to_cyrillic(ch) for ch in token)
        return "".join(_cyrillic_to_latin(ch) for ch in token)
    line = re.sub(r"[A-Za-zА-Яа-яЁё]+", repair_token, line)
    return line


def _latin_to_cyrillic(char: str) -> str:
    return {
        "A": "А", "a": "а",
        "B": "В", "b": "Ь", "E": "Е", "e": "е",
        "K": "К", "k": "к",
        "M": "М", "m": "т", "H": "Н",
        "O": "О", "o": "о",
        "P": "Р", "p": "р",
        "C": "С", "c": "с",
        "T": "Т", "t": "т", "y": "у",
        "X": "Х", "x": "х",
    }.get(char, char)


def _cyrillic_to_latin(char: str) -> str:
    return {
        "А": "A", "а": "a",
        "В": "B",
        "Е": "E", "е": "e",
        "К": "K", "к": "k",
        "М": "M",
        "Н": "H",
        "О": "O", "о": "o",
        "Р": "P", "р": "p",
        "С": "C", "с": "c",
        "Т": "T",
        "Х": "X",
    }.get(char, char)


def enrich_payment_document_text(text: str, *, runtime: ExtractionRuntime) -> str:
    normalized = runtime.normalize_text(text)
    if "платежное поручение" not in normalized and "банковский ордер" not in normalized:
        return text
    fields = extract_fields(text, normalize_text=runtime.normalize_text)
    return normalize_extracted_text(enrich_text_from_fields(text, fields, normalize_text=runtime.normalize_text))


def looks_like_pdf_source_dump(text: str) -> bool:
    cleaned = normalize_extracted_text(text)
    if not cleaned:
        return False
    syntax_hits = sum(cleaned.count(token) for token in [
        "%PDF-",
        "endobj",
        "stream",
        "endstream",
        "/Type/",
        "/Type /",
        "/Subtype/",
        "/Subtype /",
        "/Filter/",
        "/Filter /",
        "/Length ",
        " obj",
    ])
    if syntax_hits >= 6:
        return True
    lines = cleaned.splitlines()[:40]
    pdf_like_lines = sum(
        1 for line in lines
        if line.startswith("/") or "obj" in line or "endobj" in line or "stream" in line or "endstream" in line
    )
    return pdf_like_lines >= 8


def informative_text_lines(text: str, *, runtime: ExtractionRuntime) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in normalize_extracted_text(text).splitlines():
        normalized_line = runtime.normalize_text(raw_line)
        if not normalized_line or normalized_line in seen:
            continue
        has_pattern = any(re.search(pattern, normalized_line, re.IGNORECASE) for pattern in runtime.informative_text_patterns)
        has_long_number = bool(re.search(r"\b\d{8,}\b", normalized_line))
        if not has_pattern and not has_long_number:
            continue
        seen.add(normalized_line)
        lines.append(raw_line.strip())
    return lines


def is_garbled_text(text: str) -> bool:
    stripped = "".join(ch for ch in text if not ch.isspace())
    if len(stripped) < 30:
        return True
    letters = sum(ch.isalpha() for ch in stripped)
    digits = sum(ch.isdigit() for ch in stripped)
    useful = letters + digits
    if useful < max(20, len(stripped) // 8):
        return True
    cyrillic = sum(1 for ch in stripped if "\u0400" <= ch <= "\u04FF")
    latin = sum(1 for ch in stripped if ("a" <= ch.lower() <= "z"))
    repeated_hex_tokens = len(re.findall(r"\b[0-9a-f]{4,8}\b", text.lower()))
    if repeated_hex_tokens > max(12, len(stripped) // 35):
        return True
    if cyrillic + latin < max(12, len(stripped) // 12) and repeated_hex_tokens > 6:
        return True
    replacement_like = sum(1 for ch in stripped if ord(ch) > 0xFF and not ("\u0400" <= ch <= "\u04FF"))
    if replacement_like > len(stripped) * 0.2:
        return True
    weird_bigrams = len(re.findall(r"[a-zA-Z][а-яА-Я]|[а-яА-Я][a-zA-Z]", text))
    if weird_bigrams > max(8, len(text) // 80):
        return True
    return False


def looks_like_binary_container_dump(text: str) -> bool:
    if not text:
        return False
    sample = text[:50_000]
    control = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\n\r\t")
    weird = sum(1 for ch in sample if ch in {"ˇ", "œ", "‡", "°", "±", "·", "\ufffd", "\x00"})
    non_space = sum(1 for ch in sample if not ch.isspace())
    if non_space == 0:
        return True
    if control > max(40, len(sample) // 100):
        return True
    if weird > max(80, len(sample) // 120):
        return True
    if informative_text_lines(sample, runtime=ExtractionRuntime(
        text_cache={},
        manual_review_heavy_ocr_paths=set(),
        command_exists_cache={},
        ocr_binary_candidates=[],
        swift_pdf_splitter=Path("missing.swift"),
        cache_root=Path("/tmp/cache"),
        text_cache_version="binary-check",
        informative_text_patterns=["счет", "получатель", "оплата", "интернет", "аренд", "услуг", "ндфл", "взнос", "комис"],
        normalize_text=lambda value: value.lower(),
    )):
        return False
    dense_symbols = sum(1 for ch in sample if not ch.isalnum() and not ch.isspace())
    return dense_symbols > max(400, len(sample) // 12)


def extract_legacy_xls_text(path: Path) -> str:
    try:
        payload = path.read_bytes()
    except Exception:
        return ""
    if not payload.startswith(b"\xd0\xcf\x11\xe0"):
        return ""
    try:
        decoded = payload.decode("utf-16le", errors="ignore")
    except Exception:
        return ""
    chunks: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"[A-Za-zА-Яа-яЁё0-9\"№().,:;/«»\- ]{4,160}", decoded):
        chunk = re.sub(r"\s+", " ", match.group(0)).strip(" -_.,;:/")
        if len(chunk) < 4:
            continue
        letters = sum(ch.isalpha() for ch in chunk)
        if letters < 3:
            continue
        if re.fullmatch(r"[яЯюЮэЭˇœ‡°±· ]+", chunk):
            continue
        key = chunk.lower()
        if key in seen:
            continue
        seen.add(key)
        chunks.append(chunk)
        if sum(len(item) for item in chunks) >= 24_000:
            break
    return "\n".join(chunks)


def pdf_text_score(text: str, source: str = "") -> int:
    if not text:
        return -10_000
    score = 0
    score += min(len(text), 5000) // 2
    score += sum(text.lower().count(keyword) * weight for keyword, weight in [
        ("платежное поручение", 250),
        ("счет", 120),
        ("получатель", 140),
        ("назначение платежа", 180),
        ("выплата заработной платы", 220),
        ("инн", 60),
        ("кпп", 60),
        ("итого", 80),
        ("всего к оплате", 120),
        ("сумма к оплате", 120),
        ("комитен", 120),
        ("комитерн", 120),
        ("искрателеком", 120),
        ("таттелеком", 120),
        ("бизнес-легион", 120),
        ("тестовпоставщик", 100),
        ("демопоставщик", 100),
    ])
    letters = sum(ch.isalpha() for ch in text)
    digits = sum(ch.isdigit() for ch in text)
    score += letters + digits
    pdf_syntax_hits = sum(text.count(token) for token in [
        "%PDF-",
        "endobj",
        "stream",
        "endstream",
        "/Type /Page",
        "/Type /Font",
        "/Resources <<",
        "/Length ",
        " obj\n",
    ])
    score -= pdf_syntax_hits * 300
    slash_tokens = len(re.findall(r"/[A-Za-z][A-Za-z0-9]+", text))
    if slash_tokens:
        score -= min(slash_tokens * 20, 4000)
    hex_bursts = len(re.findall(r"[0-9A-F]{20,}", text))
    if hex_bursts:
        score -= min(hex_bursts * 120, 2400)
    repeated_hex_tokens = len(re.findall(r"\b[0-9A-Fa-f]{4,8}\b", text))
    if repeated_hex_tokens:
        score -= min(repeated_hex_tokens * 120, 18000)
    if is_garbled_text(text):
        score -= 3000
    if source == "strings":
        score -= 1200
    elif source == "mdls":
        score += 300
    elif source == "ocr":
        score += 600
    elif source == "text_layer":
        score += 400
    return score


def choose_best_extracted_text(candidates: list[tuple[str, str]], *, runtime: ExtractionRuntime) -> str:
    prepared: list[tuple[str, str, int]] = []
    for source, text in candidates:
        cleaned = normalize_extracted_text(text)
        if not cleaned:
            continue
        if source in {"text_layer", "pdftotext", "mutool", "strings"} and looks_like_pdf_source_dump(cleaned):
            continue
        prepared.append((source, cleaned, pdf_text_score(cleaned, source)))
    if not prepared:
        return ""
    prepared.sort(key=lambda item: item[2], reverse=True)
    _, best_text, best_score = prepared[0]
    merged_lines = best_text.splitlines()
    seen = {runtime.normalize_text(line) for line in merged_lines if line.strip()}
    for source, text, score in prepared[1:]:
        extra_lines = informative_text_lines(text, runtime=runtime)
        if source in {"mdls", "text_layer"}:
            if score < -4000 and not extra_lines:
                continue
        elif score < max(250, best_score - 1400):
            continue
        for line in extra_lines:
            key = runtime.normalize_text(line)
            if key in seen:
                continue
            merged_lines.append(line)
            seen.add(key)
    return "\n".join(line for line in merged_lines if line.strip())


def best_candidate_quality(candidates: list[tuple[str, str]], *, runtime: ExtractionRuntime) -> tuple[str, int]:
    best_text = choose_best_extracted_text(candidates, runtime=runtime)
    if not best_text:
        return "", -10_000
    source = candidates[0][0] if candidates else ""
    return best_text, pdf_text_score(best_text, source)


def extracted_text_is_good(text: str, score: int, *, runtime: ExtractionRuntime, min_score: int = 240) -> bool:
    if not text:
        return False
    if is_garbled_text(text):
        return False
    if score < min_score:
        return False
    return bool(informative_text_lines(text, runtime=runtime) or len(text) >= 160)


def pdf_text_is_usable(text: str, score: int, *, runtime: ExtractionRuntime, min_score: int = 240) -> bool:
    if not extracted_text_is_good(text, score, runtime=runtime, min_score=min_score):
        return False
    flags = payment_text_quality_flags(text, runtime=runtime)
    if flags["is_payment_like"] and not extract_fields(text, normalize_text=runtime.normalize_text).amount_hint:
        return False
    return not should_run_heavy_ocr(text, score, runtime=runtime)


def best_pdf_candidate_quality(candidates: list[tuple[str, str]], *, runtime: ExtractionRuntime) -> tuple[str, int]:
    # Do not append damaged text-layer fields to a complete OCR result.
    usable = [(source, text) for source, text in candidates if pdf_text_is_usable(
        normalize_extracted_text(text), pdf_text_score(normalize_extracted_text(text), source), runtime=runtime,
    )]
    return best_candidate_quality(usable or candidates, runtime=runtime)


def payment_text_quality_flags(text: str, *, runtime: ExtractionRuntime) -> dict[str, bool]:
    return sorting_ocr_gate.payment_text_quality_flags(text, normalize_text=runtime.normalize_text)


def should_run_heavy_ocr(text: str, score: int, *, runtime: ExtractionRuntime) -> bool:
    return sorting_ocr_gate.should_run_heavy_ocr(
        text,
        score,
        normalize_text=runtime.normalize_text,
        is_garbled_text=is_garbled_text,
        informative_text_lines=lambda value: informative_text_lines(value, runtime=runtime),
    )


def extraction_gate_decision(path: Path, text: str, score: int, *, runtime: ExtractionRuntime):
    profile = build_document_profile(
        path,
        runtime=runtime,
        file_text_fn=lambda _: text,
        extract_pdf_text_layer=extract_pdf_text_layer,
    )
    fields = extract_fields(text, normalize_text=runtime.normalize_text)
    informative_lines = informative_text_lines(text, runtime=runtime)
    normalized = runtime.normalize_text(text)
    is_payment_like = "платежное поручение" in normalized or "банковский ордер" in normalized
    return decide_ocr_gate(
        profile=profile,
        text=text,
        score=score,
        informative_lines=informative_lines,
        is_garbled_text=is_garbled_text(text),
        fields=fields,
        is_payment_like=is_payment_like,
    )


def _read_archive_member_text(archive: zipfile.ZipFile, name: str, *, limit: int) -> str:
    try:
        with archive.open(name) as member:
            payload = member.read(limit + 1)
    except Exception:
        return ""
    if len(payload) > limit:
        return ""
    return payload.decode("utf-8", errors="ignore")


def _collect_openxml_sheet_names(archive: zipfile.ZipFile) -> list[str]:
    names = sorted(
        name
        for name in archive.namelist()
        if name.startswith("xl/worksheets/") and name.endswith(".xml")
    )
    return names[:OPENXML_WORKSHEETS_LIMIT]


def _extract_xml_text(raw_xml: str) -> str:
    if not raw_xml:
        return ""
    try:
        root = ET.fromstring(raw_xml)
        parts = [node.strip() for node in root.itertext() if node and node.strip()]
        return " ".join(parts)
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw_xml)


def read_openxml_text(path: Path, *, suffix: str = "") -> str:
    chunks: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            if suffix in {".xlsx", ".xlsm"}:
                selected_names = [
                    "docProps/core.xml",
                    "docProps/app.xml",
                    "xl/workbook.xml",
                    "xl/sharedStrings.xml",
                    *_collect_openxml_sheet_names(archive),
                ]
                for name in selected_names:
                    if name not in archive.namelist():
                        continue
                    limit = OPENXML_SHARED_STRINGS_BYTES_LIMIT if name == "xl/sharedStrings.xml" else OPENXML_XML_BYTES_LIMIT
                    raw_xml = _read_archive_member_text(archive, name, limit=limit)
                    text = _extract_xml_text(raw_xml)
                    if text:
                        chunks.append(text)
                        if sum(len(chunk) for chunk in chunks) >= OPENXML_TEXT_CHAR_LIMIT:
                            break
            else:
                for name in archive.namelist():
                    if not name.endswith(".xml"):
                        continue
                    raw_xml = _read_archive_member_text(archive, name, limit=OPENXML_XML_BYTES_LIMIT)
                    text = _extract_xml_text(raw_xml)
                    if text:
                        chunks.append(text)
                        if sum(len(chunk) for chunk in chunks) >= OPENXML_TEXT_CHAR_LIMIT:
                            break
    except Exception:
        return ""
    return " ".join(chunks)[:OPENXML_TEXT_CHAR_LIMIT]


def command_exists(name: str, *, runtime: ExtractionRuntime) -> bool:
    cached = runtime.command_exists_cache.get(name)
    if cached is not None:
        return cached
    exists = shutil.which(name) is not None
    runtime.command_exists_cache[name] = exists
    return exists


def read_textutil_text(path: Path) -> str:
    if not platform_support.is_macos():
        return ""
    return _run_command(["textutil", "-convert", "txt", "-stdout", str(path)], timeout=60)


def available_ocr_binary(*, runtime: ExtractionRuntime) -> Path | None:
    override = os.environ.get("SORTING_OCR_BINARY", "").strip()
    if override:
        resolved = Path(override).expanduser()
        if resolved.exists() and os.access(resolved, os.X_OK):
            return resolved
    for candidate in runtime.ocr_binary_candidates:
        resolved = candidate if candidate.is_absolute() else Path.cwd() / candidate
        if resolved.exists() and os.access(resolved, os.X_OK):
            return resolved
    return None


def read_sips_ocr_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    ocr_binary = available_ocr_binary(runtime=runtime)
    if not ocr_binary:
        return ""
    if not platform_support.is_macos():
        return ""
    with tempfile.TemporaryDirectory(prefix="imgocr_") as tmpdir:
        output = Path(tmpdir) / "normalized.png"
        converted = subprocess.run(["sips", "-s", "format", "png", str(path), "--out", str(output)], capture_output=True, text=True, timeout=90, check=False)
        if converted.returncode != 0 or not output.exists():
            return ""
        return _run_command([str(ocr_binary), str(output), "1"], timeout=90)


def read_pdf_native_ocr_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    ocr_binary = available_ocr_binary(runtime=runtime)
    if not ocr_binary:
        return ""
    pages = platform_support.pdf_page_count(path) or 4
    output = _run_command([str(ocr_binary), str(path), str(pages), "--force-ocr", "--quality-json"],
                          timeout=min(120, max(40, pages * 20)))
    return decode_native_ocr_result(output, path, runtime=runtime)


def decode_native_ocr_result(output: str, path: Path, *, runtime: ExtractionRuntime) -> str:
    if not output.lstrip().startswith("{"):
        return output
    try:
        result = json.loads(output)
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ValueError("Invalid OCR quality result")
        if result.get("incomplete_pages"):
            runtime.manual_review_heavy_ocr_paths.add(path)
            _log_extraction(f"{path.name}: unreadable pages {result['incomplete_pages']} -> manual review")
        return result["text"]
    except (ValueError, TypeError):
        runtime.manual_review_heavy_ocr_paths.add(path)
        return ""


def pdf_has_unreadable_image_pages(path: Path, *, runtime: ExtractionRuntime) -> bool:
    if fitz is None:
        return False
    try:
        with fitz.open(path) as document:
            for page in document:
                if page.get_images():
                    text = normalize_extracted_text(page.get_text("text"))
                    if not pdf_text_is_usable(text, pdf_text_score(text, "pymupdf"), runtime=runtime):
                        return True
    except Exception:
        return False
    return False


def short_vector_text_is_readable(path: Path, text: str) -> bool:
    if fitz is None or not 4 <= len(text) < 160:
        return False
    normalized = text.lower()
    if "платежное поручение" in normalized or "банковский ордер" in normalized:
        return False
    if not re.fullmatch(r"[A-Za-zА-Яа-яЁё0-9\s.,:;№#()\"«»/\-]+", text):
        return False
    if sum(char.isalpha() for char in text) < 4:
        return False
    try:
        with fitz.open(path) as document:
            return not any(page.get_images() for page in document)
    except Exception:
        return False


def read_mdls_text(path: Path) -> str:
    if not platform_support.is_macos():
        return ""
    keys = [
        "kMDItemTextContent",
        "kMDItemTitle",
        "kMDItemDisplayName",
        "kMDItemSubject",
        "kMDItemAuthors",
        "kMDItemKeywords",
        "kMDItemComment",
        "kMDItemRecipientEmailAddresses",
        "kMDItemAuthorEmailAddresses",
    ]
    parts: list[str] = []
    for key in keys:
        value = _run_command(["mdls", "-raw", "-name", key, str(path)], timeout=20)
        if value.strip() and value.strip() != "(null)":
            parts.append(value)
    return "\n".join(parts)


def read_pdftotext_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    if not command_exists("pdftotext", runtime=runtime):
        return ""
    return _run_command(["pdftotext", "-layout", "-nopgbrk", str(path), "-"], timeout=120)


def read_pymupdf_text(path: Path) -> str:
    if fitz is None:
        return ""
    try:
        with fitz.open(path) as document:
            parts: list[str] = []
            for page in document:
                logical = page.get_text("text")
                # Invoice field labels can be vertically centered beside multiline values.
                text = logical if re.search(r"поставщик\s*(?:\([^)]*\))?\s*:", logical, re.I) else page.get_text("text", sort=True)
                if text.strip():
                    parts.append(text)
            return normalize_extracted_text("\n".join(parts))
    except Exception:
        return ""


def read_mutool_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    if not command_exists("mutool", runtime=runtime):
        return ""
    return _run_command(["mutool", "draw", "-F", "txt", "-o", "-", str(path)], timeout=120)


def read_tesseract_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    if not command_exists("tesseract", runtime=runtime):
        return ""
    return _run_command(["tesseract", str(path), "stdout", "-l", "rus+eng", "--psm", "6"], timeout=180)


def read_ocrmypdf_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    if not command_exists("ocrmypdf", runtime=runtime) or not command_exists("pdftotext", runtime=runtime):
        return ""
    with tempfile.TemporaryDirectory(prefix="ocrmypdf_") as tmpdir:
        output = Path(tmpdir) / "ocr.pdf"
        result = subprocess.run(["ocrmypdf", "--skip-text", "--sidecar", os.devnull, str(path), str(output)], capture_output=True, text=True, timeout=240, check=False)
        if result.returncode != 0 or not output.exists():
            return ""
        return read_pdftotext_text(output, runtime=runtime)


def ocr_via_rendered_image(path: Path, ocr_binary: Path) -> str:
    if not platform_support.is_macos():
        return ""
    with tempfile.TemporaryDirectory(prefix="pdfocr_") as tmpdir:
        image_path = Path(tmpdir) / "page.png"
        converted = subprocess.run(["sips", "-s", "format", "png", str(path), "--out", str(image_path)], capture_output=True, text=True, timeout=60, check=False)
        if converted.returncode != 0 or not image_path.exists():
            return ""
        return _run_command([str(ocr_binary), str(image_path), "1"], timeout=120)


def read_quicklook_ocr_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    ocr_binary = available_ocr_binary(runtime=runtime)
    if not ocr_binary:
        return ""
    if not platform_support.is_macos():
        return ""
    best_text = ""
    best_score = -10_000
    for size in (2400,):
        with tempfile.TemporaryDirectory(prefix="qlocr_") as tmpdir:
            output_dir = Path(tmpdir)
            try:
                rendered = subprocess.run(["qlmanage", "-t", "-s", str(size), "-o", str(output_dir), str(path)], capture_output=True, text=True, timeout=15, check=False)
            except (OSError, subprocess.TimeoutExpired):
                return best_text
            if rendered.returncode != 0:
                continue
            preview_candidates = sorted(output_dir.glob("*.png")) + sorted(output_dir.glob("*.jpg")) + sorted(output_dir.glob("*.jpeg"))
            for preview in preview_candidates:
                text = _run_command([str(ocr_binary), str(preview), "1"], timeout=20)
                if not text.strip():
                    continue
                score = pdf_text_score(text, "ocr")
                if score > best_score:
                    best_score = score
                    best_text = text
    return best_text


def parse_pdf_cmap(text: str) -> dict[int, str]:
    cmap: dict[int, str] = {}
    for line in text.splitlines():
        line = line.strip()
        bfchar = re.match(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>$", line)
        if bfchar:
            cmap[int(bfchar.group(1), 16)] = chr(int(bfchar.group(2), 16))
            continue
        bfrange = re.match(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>$", line)
        if bfrange:
            start, end, target = [int(item, 16) for item in bfrange.groups()]
            if end < start or end - start > 65535 or target + end - start > 0x10FFFF:
                continue
            for offset, code in enumerate(range(start, end + 1)):
                cmap[code] = chr(target + offset)
    return cmap


def pdf_unescape(raw: bytes) -> bytes:
    result = bytearray()
    index = 0
    while index < len(raw):
        value = raw[index]
        if value == 0x5C and index + 1 < len(raw):
            index += 1
            escaped = raw[index]
            mapping = {
                ord("n"): 0x0A,
                ord("r"): 0x0D,
                ord("t"): 0x09,
                ord("b"): 0x08,
                ord("f"): 0x0C,
                ord("("): 0x28,
                ord(")"): 0x29,
                ord("\\"): 0x5C,
            }
            if escaped in mapping:
                result.append(mapping[escaped])
            elif 48 <= escaped <= 55:
                octal = [escaped]
                for _ in range(2):
                    if index + 1 < len(raw) and 48 <= raw[index + 1] <= 55:
                        index += 1
                        octal.append(raw[index])
                    else:
                        break
                result.append(int(bytes(octal), 8))
            else:
                result.append(escaped)
        else:
            result.append(value)
        index += 1
    return bytes(result)


def decode_pdf_string(raw: bytes, cmap: dict[int, str], hex_mode: bool = False) -> str:
    payload = bytes.fromhex(raw.decode("ascii")) if hex_mode else pdf_unescape(raw)
    if cmap and len(payload) % 2 == 0:
        chars: list[str] = []
        hits = 0
        for index in range(0, len(payload), 2):
            code = int.from_bytes(payload[index:index + 2], "big")
            char = cmap.get(code)
            if char is None and 32 <= code < 127:
                char = chr(code)
            if char:
                chars.append(char)
                hits += 1
        if hits:
            return "".join(chars)
    return payload.decode("utf-8", errors="ignore") or payload.decode("latin1", errors="ignore")


def extract_pdf_strings(stream: bytes, cmap: dict[int, str]) -> list[str]:
    results: list[str] = []
    literal = rb"\(((?:\\.|[^()\\]){0,4096})\)"
    results.extend(decode_pdf_string(match.group(1), cmap) for match in re.finditer(literal + rb"\s{0,32}Tj", stream, re.S))
    results.extend(decode_pdf_string(match.group(1), cmap, hex_mode=True) for match in re.finditer(rb"<([0-9A-Fa-f]{2,8192})>\s{0,32}Tj", stream))
    for match in re.finditer(rb"\[([^\[\]]{0,32768})\]\s{0,32}TJ", stream, re.S):
        chunk = match.group(1)
        parts = re.findall(literal + rb"|<([0-9A-Fa-f]{2,8192})>", chunk, re.S)
        text = "".join(decode_pdf_string(part[0] or part[1], cmap, hex_mode=bool(part[1])) for part in parts)
        if text:
            results.append(text)
    return [item for item in results if item]


def extract_pdf_text_layer(path: Path) -> str:
    if path.stat().st_size > 32_000_000:
        return ""
    data = path.read_bytes()
    streams: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        header = data[max(0, match.start() - 256):match.start()]
        if any(marker in header for marker in [b"/Subtype/Image", b"/FontFile", b"/Type/XRef", b"/ObjStm"]):
            continue
        chunk = match.group(1)
        if len(chunk) > 250_000:
            continue
        try:
            decoded = zlib.decompressobj().decompress(chunk, 2_000_001)
            if len(decoded) <= 2_000_000:
                streams.append(decoded)
            if len(streams) >= 100:
                break
        except Exception:
            continue
    cmap: dict[int, str] = {}
    for stream in streams:
        if b"begincmap" in stream:
            cmap.update(parse_pdf_cmap(stream.decode("latin1", errors="ignore")))
    pieces: list[str] = []
    for stream in streams:
        if b"Tj" not in stream and b"TJ" not in stream:
            continue
        pieces.extend(extract_pdf_strings(stream, cmap))
    return "\n".join(piece for piece in pieces if piece.strip())


def ocr_pdf_by_pages(path: Path, ocr_binary: Path, *, runtime: ExtractionRuntime) -> str:
    with tempfile.TemporaryDirectory(prefix="pdfpages_") as tmpdir:
        split_dir = Path(tmpdir) / "pages"
        split_dir.mkdir(parents=True, exist_ok=True)
        page_paths: list[Path] = []
        if runtime.swift_pdf_splitter.exists() and platform_support.is_macos():
            result = _run_command(["swift", str(runtime.swift_pdf_splitter), str(path), str(split_dir)], timeout=240)
            page_paths = [Path(line.strip()) for line in result.splitlines() if line.strip().endswith(".pdf")]
        if not page_paths:
            page_paths = platform_support.split_pdf_with_pymupdf(path, split_dir)
        if not page_paths:
            return ""
        chunks: list[str] = []
        for page_path in page_paths:
            page_candidates: list[tuple[str, str]] = []
            direct = extract_pdf_text_layer(page_path)
            if direct.strip():
                page_candidates.append(("text_layer", direct))
            page_ocr = _run_command([str(ocr_binary), str(page_path), "1"], timeout=120)
            if page_ocr.strip():
                page_candidates.append(("ocr", page_ocr))
            quicklook_page_ocr = read_quicklook_ocr_text(page_path, runtime=runtime)
            if quicklook_page_ocr.strip():
                page_candidates.append(("ql_ocr", quicklook_page_ocr))
            rendered_ocr = ocr_via_rendered_image(page_path, ocr_binary)
            if rendered_ocr.strip():
                page_candidates.append(("ocr_image", rendered_ocr))
            best_page = choose_best_extracted_text(page_candidates, runtime=runtime)
            if best_page.strip():
                chunks.append(best_page)
        return normalize_extracted_text("\n".join(chunks))


def read_image_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    candidates: list[tuple[str, str]] = []
    mdls_text = read_mdls_text(path)
    if mdls_text.strip():
        candidates.append(("mdls", mdls_text))
    ocr_binary = available_ocr_binary(runtime=runtime)
    if ocr_binary:
        ocr_text = _run_command([str(ocr_binary), str(path), "1"], timeout=90)
        if ocr_text.strip():
            candidates.append(("ocr", ocr_text))
    best_text, best_score = best_candidate_quality(candidates, runtime=runtime)
    if extracted_text_is_good(best_text, best_score, runtime=runtime, min_score=220):
        return best_text
    if best_text.strip() and (len(best_text) >= 80 or informative_text_lines(best_text, runtime=runtime)):
        return best_text
    quicklook_text = read_quicklook_ocr_text(path, runtime=runtime)
    if quicklook_text.strip():
        candidates.append(("ql_ocr", quicklook_text))
    sips_ocr_text = read_sips_ocr_text(path, runtime=runtime)
    if sips_ocr_text.strip():
        candidates.append(("sips_ocr", sips_ocr_text))
    best_text, best_score = best_candidate_quality(candidates, runtime=runtime)
    if extracted_text_is_good(best_text, best_score, runtime=runtime, min_score=220):
        return best_text
    tesseract_text = read_tesseract_text(path, runtime=runtime)
    if tesseract_text.strip():
        candidates.append(("tesseract", tesseract_text))
    strings_text = _run_command(["strings", "-n", "6", str(path)], timeout=20)
    if strings_text.strip():
        candidates.append(("strings", strings_text))
    return choose_best_extracted_text(candidates, runtime=runtime)


def read_legacy_document_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    candidates: list[tuple[str, str]] = []
    mdls_text = read_mdls_text(path)
    if mdls_text.strip():
        candidates.append(("mdls", mdls_text))
    if path.suffix.lower() == ".xls":
        legacy_xls_text = extract_legacy_xls_text(path)
        if legacy_xls_text.strip():
            candidates.append(("text_layer", legacy_xls_text))
    textutil_text = read_textutil_text(path)
    if textutil_text.strip() and not looks_like_binary_container_dump(textutil_text):
        candidates.append(("textutil", textutil_text))
    best_text, best_score = best_candidate_quality(candidates, runtime=runtime)
    if extracted_text_is_good(best_text, best_score, runtime=runtime, min_score=120):
        return best_text
    if len(best_text) >= 120 and informative_text_lines(best_text, runtime=runtime):
        return best_text
    quicklook_text = read_quicklook_ocr_text(path, runtime=runtime)
    if quicklook_text.strip():
        candidates.append(("ocr", quicklook_text))
    strings_text = _run_command(["strings", "-n", "6", str(path)], timeout=30)
    if strings_text.strip() and not looks_like_binary_container_dump(strings_text):
        candidates.append(("strings", strings_text))
    return choose_best_extracted_text(candidates, runtime=runtime)


def read_generic_document_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    candidates: list[tuple[str, str]] = []
    mdls_text = read_mdls_text(path)
    if mdls_text.strip():
        candidates.append(("mdls", mdls_text))
    textutil_text = read_textutil_text(path)
    if textutil_text.strip() and not looks_like_binary_container_dump(textutil_text):
        candidates.append(("textutil", textutil_text))
    best_text, best_score = best_candidate_quality(candidates, runtime=runtime)
    if extracted_text_is_good(best_text, best_score, runtime=runtime, min_score=140):
        return best_text
    if len(best_text) >= 140 and informative_text_lines(best_text, runtime=runtime):
        return best_text
    if best_text.strip() and len(best_text) >= 80:
        return best_text
    quicklook_text = read_quicklook_ocr_text(path, runtime=runtime)
    if quicklook_text.strip():
        candidates.append(("ocr", quicklook_text))
    strings_text = _run_command(["strings", "-n", "6", str(path)], timeout=30)
    if strings_text.strip() and not looks_like_binary_container_dump(strings_text):
        candidates.append(("strings", strings_text))
    return choose_best_extracted_text(candidates, runtime=runtime)


def read_pdf_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    try:
        if not path.read_bytes().startswith(b"%PDF"):
            return ""
    except Exception:
        return ""

    candidates: list[tuple[str, str]] = []
    pymupdf_text = read_pymupdf_text(path)
    unreadable_image_pages = pdf_has_unreadable_image_pages(path, runtime=runtime)
    if pymupdf_text.strip():
        cleaned = normalize_extracted_text(pymupdf_text)
        score = pdf_text_score(cleaned, "pymupdf")
        if not unreadable_image_pages and (
            pdf_text_is_usable(cleaned, score, runtime=runtime) or short_vector_text_is_readable(path, cleaned)
        ):
            return cleaned
        candidates.append(("pymupdf", cleaned))
        _log_extraction(f"{path.name}: weak PDF text layer -> OCR quality check")
    text_layer = extract_pdf_text_layer(path)
    if text_layer.strip():
        candidates.append(("text_layer", text_layer))
    pdftotext_text = read_pdftotext_text(path, runtime=runtime)
    if pdftotext_text.strip():
        candidates.append(("pdftotext", pdftotext_text))
    mutool_text = read_mutool_text(path, runtime=runtime)
    if mutool_text.strip():
        candidates.append(("mutool", mutool_text))
    best_text, best_score = best_pdf_candidate_quality(candidates, runtime=runtime)
    if not unreadable_image_pages and pdf_text_is_usable(best_text, best_score, runtime=runtime):
        return best_text
    mdls_text = read_mdls_text(path)
    if mdls_text.strip():
        candidates.append(("mdls", mdls_text))
    best_text, best_score = best_pdf_candidate_quality(candidates, runtime=runtime)
    if not unreadable_image_pages and pdf_text_is_usable(best_text, best_score, runtime=runtime):
        return best_text
    native_text = read_pdf_native_ocr_text(path, runtime=runtime)
    if native_text.strip():
        if unreadable_image_pages:
            candidates = []
        candidates.append(("ocr", native_text))
    elif unreadable_image_pages:
        runtime.manual_review_heavy_ocr_paths.add(path)
    best_text, best_score = best_pdf_candidate_quality(candidates, runtime=runtime)
    if pdf_text_is_usable(best_text, best_score, runtime=runtime):
        return best_text
    gate = extraction_gate_decision(path, best_text, best_score, runtime=runtime)
    if not gate.should_run_heavy_ocr:
        if not pdf_text_is_usable(best_text, best_score, runtime=runtime, min_score=170):
            runtime.manual_review_heavy_ocr_paths.add(path)
        _log_extraction(f"{path.name}: gate skip ({gate.reason})")
        return best_text
    if not heavy_ocr_enabled():
        runtime.manual_review_heavy_ocr_paths.add(path)
        _log_extraction(f"{path.name}: heavy OCR required -> manual review ({gate.reason})")
        strings_text = _run_command(["strings", "-n", "6", str(path)], timeout=30)
        if strings_text.strip():
            candidates.append(("strings", strings_text))
        return choose_best_extracted_text(candidates, runtime=runtime)
    ocr_binary = available_ocr_binary(runtime=runtime)
    if ocr_binary:
        _log_extraction(f"{path.name}: heavy OCR ({gate.reason})")
        pages = platform_support.pdf_page_count(path) or 4
        ocr_text = decode_native_ocr_result(
            _run_command([str(ocr_binary), str(path), str(pages), "--force-ocr", "--quality-json"], timeout=120),
            path, runtime=runtime,
        )
        if ocr_text.strip():
            candidates.append(("ocr", ocr_text))
        best_text, best_score = best_pdf_candidate_quality(candidates, runtime=runtime)
        if pdf_text_is_usable(best_text, best_score, runtime=runtime, min_score=200):
            return best_text

        if gate.should_run_rendered_image_ocr:
            _log_extraction(f"{path.name}: rendered image OCR")
            image_ocr_text = ocr_via_rendered_image(path, ocr_binary)
            if image_ocr_text.strip():
                candidates.append(("ocr_image", image_ocr_text))
            best_text, best_score = best_pdf_candidate_quality(candidates, runtime=runtime)
            if pdf_text_is_usable(best_text, best_score, runtime=runtime, min_score=190):
                return best_text

        if gate.should_run_page_by_page_ocr:
            _log_extraction(f"{path.name}: page-by-page OCR")
            page_ocr_text = ocr_pdf_by_pages(path, ocr_binary, runtime=runtime)
            if page_ocr_text.strip():
                candidates.append(("ocr_pages", page_ocr_text))
            best_text, best_score = best_pdf_candidate_quality(candidates, runtime=runtime)
            if pdf_text_is_usable(best_text, best_score, runtime=runtime, min_score=180):
                return best_text

    if gate.should_run_tesseract:
        _log_extraction(f"{path.name}: tesseract fallback")
        tesseract_text = read_tesseract_text(path, runtime=runtime)
        if tesseract_text.strip():
            candidates.append(("tesseract", tesseract_text))
        best_text, best_score = best_pdf_candidate_quality(candidates, runtime=runtime)
        if pdf_text_is_usable(best_text, best_score, runtime=runtime, min_score=170):
            return best_text

    if gate.should_run_ocrmypdf:
        _log_extraction(f"{path.name}: ocrmypdf fallback")
        ocrmypdf_text = read_ocrmypdf_text(path, runtime=runtime)
        if ocrmypdf_text.strip():
            candidates.append(("ocrmypdf", ocrmypdf_text))
    strings_text = _run_command(["strings", "-n", "6", str(path)], timeout=30)
    if strings_text.strip():
        candidates.append(("strings", strings_text))
    best_text, best_score = best_pdf_candidate_quality(candidates, runtime=runtime)
    if not pdf_text_is_usable(best_text, best_score, runtime=runtime, min_score=170):
        runtime.manual_review_heavy_ocr_paths.add(path)
    return best_text


def file_text(path: Path, *, runtime: ExtractionRuntime) -> str:
    cached = runtime.text_cache.get(path)
    if cached is not None:
        return cached
    disk_cached = load_disk_cached_text(path, runtime=runtime)
    if disk_cached is not None:
        runtime.text_cache[path] = disk_cached
        return disk_cached
    suffix = path.suffix.lower()
    try:
        if suffix in {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm", ".eml", ".rtf"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            text = enrich_payment_document_text(normalize_extracted_text(text), runtime=runtime)
            runtime.text_cache[path] = text
            save_disk_cached_text(path, text, runtime=runtime)
            return text
        if suffix in {".docx", ".xlsx", ".xlsm", ".xlsb", ".odt", ".ods", ".odp"}:
            text = enrich_payment_document_text(normalize_extracted_text(read_openxml_text(path, suffix=suffix)), runtime=runtime)
            runtime.text_cache[path] = text
            save_disk_cached_text(path, text, runtime=runtime)
            return text
        if suffix == ".pdf":
            text = enrich_payment_document_text(normalize_extracted_text(read_pdf_text(path, runtime=runtime)), runtime=runtime)
            runtime.text_cache[path] = text
            if path not in runtime.manual_review_heavy_ocr_paths:
                save_disk_cached_text(path, text, runtime=runtime)
            return text
        if suffix in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".heic", ".webp", ".avif", ".jfif", ".jp2", ".j2k"}:
            text = enrich_payment_document_text(normalize_extracted_text(read_image_text(path, runtime=runtime)), runtime=runtime)
            runtime.text_cache[path] = text
            save_disk_cached_text(path, text, runtime=runtime)
            return text
        if suffix in {".xls", ".doc", ".msg"}:
            text = enrich_payment_document_text(normalize_extracted_text(read_legacy_document_text(path, runtime=runtime)), runtime=runtime)
            runtime.text_cache[path] = text
            save_disk_cached_text(path, text, runtime=runtime)
            return text
    except Exception:
        runtime.text_cache[path] = ""
        return ""
    text = enrich_payment_document_text(normalize_extracted_text(read_generic_document_text(path, runtime=runtime)), runtime=runtime)
    runtime.text_cache[path] = text
    save_disk_cached_text(path, text, runtime=runtime)
    return text
