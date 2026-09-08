from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

PDF_MAGIC = b"%PDF-"


class RagFileStoreError(RuntimeError):
    pass


class RagFileStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_id(document_id: str) -> None:
        if not re.fullmatch(r"doc_[a-f0-9]{16,32}", document_id):
            raise RagFileStoreError("Invalid RAG document identifier.")

    def _path(self, document_id: str) -> Path:
        self._validate_id(document_id)
        path = (self.root / f"{document_id}.pdf").resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise RagFileStoreError("Invalid RAG source path.") from exc
        return path

    def save(self, document_id: str, content: bytes) -> Path:
        if not content.startswith(PDF_MAGIC):
            raise RagFileStoreError("The uploaded file is not a valid PDF.")
        target = self._path(document_id)
        with target.open("xb") as handle:
            handle.write(content)
        return target

    def get(self, document_id: str) -> Path:
        path = self._path(document_id)
        if not path.is_file() or path.is_symlink():
            raise RagFileStoreError("The indexed source document is unavailable.")
        return path

    def delete(self, document_id: str) -> None:
        path = self._path(document_id)
        path.unlink(missing_ok=True)

    @staticmethod
    def fingerprint(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def cleanup(self) -> None:
        for child in self.root.iterdir():
            if child.is_file() and not child.is_symlink():
                child.unlink(missing_ok=True)
            elif child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
