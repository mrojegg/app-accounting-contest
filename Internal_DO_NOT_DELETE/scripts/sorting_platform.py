from __future__ import annotations

import platform
import tempfile
from pathlib import Path

try:
    import fitz  # type: ignore
except Exception:
    fitz = None


def is_macos() -> bool:
    return platform.system() == "Darwin"


def make_temp_dir(*, prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


def pdf_page_count(path: Path) -> int:
    if fitz is None:
        return 1
    try:
        with fitz.open(path) as document:
            return max(document.page_count, 1)
    except Exception:
        return 1


def pdf_has_text_layer(path: Path) -> bool:
    if fitz is None:
        return False
    try:
        with fitz.open(path) as document:
            for page in document:
                text = page.get_text("text")
                if text and text.strip():
                    return True
    except Exception:
        return False
    return False


def pdf_has_text_layer(path: Path) -> bool:
    if fitz is None:
        return False
    try:
        with fitz.open(path) as document:
            for page in document:
                text = page.get_text("text")
                if text and text.strip():
                    return True
    except Exception:
        return False
    return False


def split_pdf_with_pymupdf(path: Path, output_dir: Path) -> list[Path]:
    if fitz is None:
        return []
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        with fitz.open(path) as source:
            if source.page_count <= 1:
                return [path]
            results: list[Path] = []
            for index in range(source.page_count):
                target = fitz.open()
                try:
                    target.insert_pdf(source, from_page=index, to_page=index)
                    out = output_dir / f"{path.stem}_page_{index + 1:04d}.pdf"
                    target.save(out)
                    results.append(out)
                finally:
                    target.close()
            return results
    except Exception:
        return []
