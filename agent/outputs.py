from __future__ import annotations

import re
import threading
import textwrap
import uuid
from pathlib import Path
from typing import Any

import pymupdf


class AgentOutputManager:
    MAX_FILENAME = 120

    def __init__(self, root: str | Path, max_file_bytes: int = 2_000_000):
        self.root = Path(root).resolve()
        self.max_file_bytes = max_file_bytes
        self._files: dict[str, tuple[str, Path]] = {}
        self._lock = threading.RLock()

    def _session_dir(self, session_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", session_id):
            raise ValueError("Invalid session ID.")
        target = (self.root / session_id).resolve()
        target.relative_to(self.root)
        target.mkdir(parents=True, exist_ok=True)
        return target

    @classmethod
    def _safe_filename(cls, filename: str, extension: str) -> str:
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("Output filename is required.")
        if any(token in filename for token in ("/", "\\", "..", ":")):
            raise ValueError("Output filename must not contain a path.")
        stem = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(filename).stem).strip("._")[: cls.MAX_FILENAME - len(extension)]
        if not stem:
            raise ValueError("Output filename is invalid.")
        return f"{stem}{extension}"

    def _metadata(self, session_id: str, filename: str, path: Path, media_type: str) -> dict[str, Any]:
        if not path.is_file():
            raise IOError("Generated file was not created.")
        size = path.stat().st_size
        if size <= 0 or size > self.max_file_bytes:
            raise IOError("Generated file size is outside the allowed limit.")
        output_id = f"out_{uuid.uuid4().hex}"
        with self._lock:
            self._files[output_id] = (session_id, path)
        return {"output_id": output_id, "filename": filename, "size_bytes": size, "media_type": media_type, "download_url": f"/api/agent/outputs/{output_id}"}

    def generate_txt(self, session_id: str, filename: str, content: str) -> dict[str, Any]:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("TXT content is required.")
        safe = self._safe_filename(filename, ".txt")
        path = self._session_dir(session_id) / safe
        path.write_text(content, encoding="utf-8", newline="\n")
        path.read_text(encoding="utf-8")
        return self._metadata(session_id, safe, path, "text/plain; charset=utf-8")

    def generate_pdf(self, session_id: str, filename: str, content: str) -> dict[str, Any]:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("PDF content is required.")
        safe = self._safe_filename(filename, ".pdf")
        path = self._session_dir(session_id) / safe
        pdf = pymupdf.open()
        try:
            lines: list[str] = []
            raw_lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            while raw_lines and not raw_lines[-1].strip():
                raw_lines.pop()
            for raw_line in raw_lines:
                if not raw_line.strip():
                    lines.append("")
                    continue
                lines.extend(textwrap.wrap(raw_line, width=96, break_long_words=True, break_on_hyphens=False) or [""])

            page = pdf.new_page()
            y = 54
            line_height = 14
            bottom = page.rect.height - 54
            for line in lines:
                if y + line_height > bottom:
                    page = pdf.new_page()
                    y = 54
                    bottom = page.rect.height - 54
                if line:
                    page.insert_text((50, y), line, fontsize=10, fontname="helv", color=(0, 0, 0))
                y += line_height
            if not any(line.strip() for line in lines):
                raise IOError("Generated PDF has no report text.")
            page_count = len(pdf)
            for index, page in enumerate(pdf, 1):
                page.insert_text((page.rect.width - 78, page.rect.height - 28), f"Page {index} of {page_count}", fontsize=8, fontname="helv", color=(0.35, 0.35, 0.35))
            pdf.save(str(path))
        finally:
            pdf.close()
        if path.read_bytes()[:5] != b"%PDF-":
            raise IOError("Generated PDF signature verification failed.")
        return self._metadata(session_id, safe, path, "application/pdf")

    def resolve(self, output_id: str, session_id: str) -> Path:
        with self._lock:
            record = self._files.get(output_id)
        if not record or record[0] != session_id:
            raise PermissionError("Output file not found or access denied.")
        path = record[1].resolve()
        path.relative_to(self._session_dir(session_id))
        if not path.is_file():
            raise FileNotFoundError("Output file is no longer available.")
        return path

    def cleanup_session(self, session_id: str) -> None:
        with self._lock:
            stale = [key for key, value in self._files.items() if value[0] == session_id]
            for key in stale:
                self._files.pop(key, None)
        target = (self.root / session_id).resolve()
        try:
            target.relative_to(self.root)
        except ValueError:
            return
        if target.is_dir():
            for child in target.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            target.rmdir()
