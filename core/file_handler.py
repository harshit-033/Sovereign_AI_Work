from __future__ import annotations

import logging
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
PDF_MAGIC = b"%PDF-"
MAX_FILENAME_LENGTH = 120


class FileHandler:
    def __init__(self, base_upload_dir: str = "uploads"):
        self.base_upload_dir = Path(base_upload_dir).resolve()
        self.base_upload_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        clean = Path(filename or "").name
        clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", clean).strip("._")
        if not clean:
            clean = f"document_{uuid.uuid4().hex[:8]}.pdf"
        stem = Path(clean).stem[: MAX_FILENAME_LENGTH - 4] or "document"
        return f"{stem}.pdf"

    @staticmethod
    def _validate_identifier(value: str, label: str) -> None:
        if not value or not re.fullmatch(r"[a-zA-Z0-9_-]+", value):
            raise ValueError(f"Invalid {label}.")

    def _inside_upload_root(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.base_upload_dir)
            return True
        except ValueError:
            return False

    def get_session_dir(self, session_id: str, create: bool = True) -> Path:
        self._validate_identifier(session_id, "session ID")
        session_dir = (self.base_upload_dir / session_id).resolve()
        if not self._inside_upload_root(session_dir):
            raise ValueError("Invalid upload path.")
        if create:
            session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def save_uploaded_file(
        self, session_id: str, original_filename: str, file_bytes: bytes
    ) -> tuple[str, Path]:
        if not file_bytes.startswith(PDF_MAGIC):
            raise ValueError("The uploaded file is not a valid PDF.")

        sanitized_name = self.sanitize_filename(original_filename)
        doc_id = str(uuid.uuid4())
        session_dir = self.get_session_dir(session_id)
        target_path = (session_dir / f"{doc_id}_{sanitized_name}").resolve()
        if target_path.parent != session_dir or not self._inside_upload_root(target_path):
            raise ValueError("Invalid file destination.")

        with target_path.open("xb") as handle:
            handle.write(file_bytes)
        logger.info("Saved PDF '%s' for session %s", sanitized_name, session_id)
        return doc_id, target_path

    def get_file_path(self, session_id: str, doc_id: str) -> Optional[Path]:
        self._validate_identifier(doc_id, "document ID")
        session_dir = self.get_session_dir(session_id, create=False)
        if not session_dir.is_dir():
            return None
        prefix = f"{doc_id}_"
        for path in session_dir.iterdir():
            if path.is_file() and not path.is_symlink() and path.name.startswith(prefix):
                return path
        return None

    def delete_file(self, path: str | Path) -> bool:
        target = Path(path).resolve()
        if not self._inside_upload_root(target) or target == self.base_upload_dir:
            raise ValueError("Refusing to delete a file outside the upload directory.")
        if not target.exists():
            return True
        if not target.is_file() or target.is_symlink():
            return False
        for attempt in range(3):
            try:
                target.unlink(missing_ok=True)
                return True
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.05 * (attempt + 1))
        logger.warning("Could not remove locked upload '%s'", target.name)
        return False

    def delete_session_files(self, session_id: str) -> None:
        try:
            session_dir = self.get_session_dir(session_id, create=False)
            if session_dir.is_dir() and not session_dir.is_symlink():
                shutil.rmtree(session_dir)
                logger.info("Deleted upload directory for session %s", session_id)
        except (OSError, ValueError) as exc:
            logger.warning("Failed to delete session files for %s: %s", session_id, exc)

    def delete_all_temp_files(self) -> None:
        for child in self.base_upload_dir.iterdir():
            try:
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                elif child.is_file() and not child.is_symlink():
                    child.unlink()
            except OSError as exc:
                logger.warning("Could not clean temporary upload '%s': %s", child.name, exc)
