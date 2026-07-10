"""Persistent subject workspaces, local materials, and per-run reports."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from structflow.evidence import EvidenceRecord


SUPPORTED_MATERIAL_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".rst",
    ".csv",
    ".json",
    ".pdf",
    ".doc",
    ".docx",
}


def safe_subject_name(value: str) -> str:
    normalized = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", value.strip())
    normalized = re.sub(r"\s+", "_", normalized).strip("._")
    return normalized or "research_subject"


@dataclass(frozen=True)
class ResearchWorkspace:
    base_dir: Path
    subject: str

    @property
    def slug(self) -> str:
        return safe_subject_name(self.subject)

    @property
    def root(self) -> Path:
        return self.base_dir / self.slug

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def search_dir(self) -> Path:
        return self.data_dir / "search"

    @property
    def materials_dir(self) -> Path:
        return self.data_dir / "materials"

    @property
    def report_dir(self) -> Path:
        return self.root / "report"

    @property
    def search_cache_file(self) -> Path:
        return self.search_dir / "search_data.json"

    def prepare(self) -> None:
        for path in (
            self.search_dir,
            self.materials_dir / "originals",
            self.materials_dir / "extracted",
            self.report_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def create_report_run(self, timestamp: str | None = None) -> Path:
        self.prepare()
        run_id = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = self.report_dir / run_id
        suffix = 1
        while candidate.exists():
            candidate = self.report_dir / f"{run_id}_{suffix:02d}"
            suffix += 1
        candidate.mkdir(parents=True)
        return candidate

    def migrate_legacy_cache(self) -> Path | None:
        """Reuse the newest legacy scans/<subject>_<timestamp>/ data once."""
        self.prepare()
        if self.search_cache_file.exists():
            return self.search_cache_file
        candidates = sorted(
            self.base_dir.glob(f"{self.slug}_*/search_data.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None
        shutil.copy2(candidates[0], self.search_cache_file)
        legacy_profile = candidates[0].parent / "entity_profile.json"
        target_profile = self.data_dir / "entity_profile.json"
        if legacy_profile.exists() and not target_profile.exists():
            shutil.copy2(legacy_profile, target_profile)
        return self.search_cache_file


class MaterialLibrary:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.originals_dir = self.root / "originals"
        self.extracted_dir = self.root / "extracted"
        self.manifest_path = self.root / "manifest.json"
        self.prepare()

    def prepare(self) -> None:
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)

    def _load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {"version": 1, "materials": []}
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "materials": []}
        if not isinstance(payload.get("materials"), list):
            payload["materials"] = []
        return payload

    def _save_manifest(self, payload: dict) -> None:
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _files(paths: Iterable[str | Path]) -> list[Path]:
        files: list[Path] = []
        for value in paths:
            path = Path(value).expanduser()
            if path.is_dir():
                files.extend(
                    item
                    for item in path.rglob("*")
                    if item.is_file()
                    and item.suffix.lower() in SUPPORTED_MATERIAL_SUFFIXES
                )
            elif path.is_file() and path.suffix.lower() in SUPPORTED_MATERIAL_SUFFIXES:
                files.append(path)
            elif path.exists():
                raise ValueError(f"Unsupported material format: {path}")
            else:
                raise FileNotFoundError(f"Material does not exist: {path}")
        return files

    def sync(self, paths: Iterable[str | Path] = ()) -> dict:
        """Import supplied files and process files dropped into materials/."""
        self.prepare()
        direct_files = [
            path
            for path in self.root.iterdir()
            if path.is_file()
            and path.name != self.manifest_path.name
            and path.suffix.lower() in SUPPORTED_MATERIAL_SUFFIXES
        ]
        source_files = self._files(paths)
        source_files.extend(direct_files)
        source_files.extend(
            path
            for path in self.originals_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_MATERIAL_SUFFIXES
        )

        payload = self._load_manifest()
        by_hash = {
            item["sha256"]: item
            for item in payload["materials"]
            if item.get("sha256")
        }
        errors: list[str] = []
        for source in source_files:
            raw = source.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if (
                digest in by_hash
                and by_hash[digest].get("status") == "ready"
            ):
                continue
            if digest in by_hash:
                payload["materials"].remove(by_hash[digest])
            stored_name = f"{digest[:12]}_{safe_subject_name(source.name)}"
            stored_path = self.originals_dir / stored_name
            if source.resolve() != stored_path.resolve():
                shutil.copy2(source, stored_path)
            else:
                stored_path = source
            extracted_path = self.extracted_dir / f"{digest}.txt"
            try:
                text = self._extract(stored_path)
                if not text.strip():
                    raise ValueError("no extractable text")
                extracted_path.write_text(text, encoding="utf-8")
                item = {
                    "sha256": digest,
                    "name": source.name,
                    "format": source.suffix.lower().lstrip("."),
                    "original": str(stored_path.relative_to(self.root)),
                    "extracted": str(extracted_path.relative_to(self.root)),
                    "source_path": str(source.resolve()),
                    "size_bytes": len(raw),
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "status": "ready",
                }
                payload["materials"].append(item)
                by_hash[digest] = item
            except Exception as error:
                errors.append(f"{source}: {error}")
                payload["materials"].append({
                    "sha256": digest,
                    "name": source.name,
                    "format": source.suffix.lower().lstrip("."),
                    "original": str(stored_path.relative_to(self.root)),
                    "source_path": str(source.resolve()),
                    "size_bytes": len(raw),
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "status": "error",
                    "error": str(error),
                })
                by_hash[digest] = payload["materials"][-1]
        self._save_manifest(payload)
        return {
            "ready": sum(
                item.get("status") == "ready" for item in payload["materials"]
            ),
            "errors": errors,
        }

    @staticmethod
    def _extract(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".md", ".markdown", ".txt", ".rst", ".csv", ".json"}:
            return path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            from docx import Document

            document = Document(str(path))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        if suffix == ".doc":
            commands = (
                ["textutil", "-convert", "txt", "-stdout", str(path)],
                ["antiword", str(path)],
            )
            for command in commands:
                try:
                    result = subprocess.run(
                        command,
                        check=True,
                        capture_output=True,
                        timeout=60,
                    )
                    return result.stdout.decode("utf-8", errors="replace")
                except (FileNotFoundError, subprocess.SubprocessError):
                    continue
            raise RuntimeError(".doc extraction requires textutil or antiword")
        raise ValueError(f"Unsupported material format: {suffix}")

    @staticmethod
    def _chunks(text: str, max_chars: int = 12_000) -> list[str]:
        paragraphs = re.split(r"\n\s*\n", text)
        chunks: list[str] = []
        current: list[str] = []
        current_size = 0
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) > max_chars:
                if current:
                    chunks.append("\n\n".join(current))
                    current, current_size = [], 0
                chunks.extend(
                    paragraph[index:index + max_chars]
                    for index in range(0, len(paragraph), max_chars)
                )
                continue
            if current and current_size + len(paragraph) + 2 > max_chars:
                chunks.append("\n\n".join(current))
                current, current_size = [], 0
            current.append(paragraph)
            current_size += len(paragraph) + 2
        if current:
            chunks.append("\n\n".join(current))
        return chunks

    def evidence_records(self) -> list[EvidenceRecord]:
        payload = self._load_manifest()
        records: list[EvidenceRecord] = []
        for item in payload["materials"]:
            if item.get("status") != "ready" or not item.get("extracted"):
                continue
            extracted = self.root / item["extracted"]
            if not extracted.exists():
                continue
            text = extracted.read_text(encoding="utf-8", errors="replace")
            chunks = self._chunks(text)
            for index, chunk in enumerate(chunks, start=1):
                records.append(EvidenceRecord(
                    category="user_material",
                    provider="local_material",
                    query=f"material:{item['sha256']}",
                    title=f"{item['name']} [part {index}/{len(chunks)}]",
                    url=f"material://{item['sha256']}/part-{index}",
                    content=chunk,
                    published_at=None,
                    source_type="user_material",
                    relevance_score=0.85,
                    quality_score=0.85,
                    freshness_score=0.5,
                ))
        return records
