from __future__ import annotations

import os
from pathlib import Path
import subprocess


def resolve_merger_binary() -> Path | None:
    override = os.environ.get("SORTING_PDF_MERGER", "").strip()
    candidates = [Path(override).expanduser()] if override else []
    candidates.append(Path(__file__).resolve().parents[1] / "pdf" / "bin" / "pdf_merge_helper")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def merge_ordered_pdfs(input_paths: list[Path], output: Path, merger_binary: Path | None = None) -> Path | None:
    output = output.expanduser().resolve()
    sources = [path.expanduser().resolve() for path in input_paths if path.is_file() and path.resolve() != output]
    if not sources:
        return None

    output.parent.mkdir(parents=True, exist_ok=True)
    binary = merger_binary or resolve_merger_binary()
    if binary is not None:
        completed = subprocess.run(
            [str(binary), str(output), *[str(path) for path in sources]],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "неизвестная ошибка"
            raise RuntimeError(f"Не удалось объединить PDF: {message}")
        return output

    try:
        import fitz
    except ImportError as error:
        raise RuntimeError("Внутренний модуль объединения PDF не найден.") from error

    merged = fitz.open()
    temporary = output.with_name(f".{output.stem}.{os.getpid()}.tmp.pdf")
    try:
        for path in sources:
            with fitz.open(path) as source:
                required = fitz.PDF_PERM_COPY | fitz.PDF_PERM_ASSEMBLE
                if source.needs_pass or source.permissions & required != required:
                    raise RuntimeError(f"PDF защищен паролем или запрещает объединение: {path}")
                if source.page_count == 0:
                    raise RuntimeError(f"В PDF нет страниц: {path}")
                merged.insert_pdf(source)
        if merged.page_count == 0:
            return None
        merged.save(temporary)
        os.replace(temporary, output)
    finally:
        merged.close()
        temporary.unlink(missing_ok=True)
    return output
