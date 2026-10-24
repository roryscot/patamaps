"""Bound source payloads and retain Markdown-reachable acceptance evidence."""
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import re
import os
import stat

MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_EVIDENCE_BYTES = 32 * 1024 * 1024
MAX_EVIDENCE_FILES = 512

class PackageScopeError(ValueError):
    pass

class SourcePayload:
    def __init__(self, root, maximum_bytes=MAX_SOURCE_BYTES, maximum_files=16384):
        self.root = Path(root).resolve()
        self.maximum_bytes = maximum_bytes
        self.maximum_files = maximum_files
        self.files = {}
        self.total_bytes = 0

    def add(self, name, path):
        name = PurePosixPath(name)
        if name.is_absolute() or ".." in name.parts:
            raise PackageScopeError("Unsafe source member")
        path = Path(path)
        if not path.resolve().is_relative_to(self.root):
            raise PackageScopeError("Source file escapes package root")
        if name.as_posix() not in self.files and len(self.files) >= self.maximum_files:
            raise PackageScopeError("Source member limit exceeded")
        before = path.stat()
        if not stat.S_ISREG(before.st_mode):
            raise PackageScopeError("Source member is not a regular file")
        previous = len(self.files.get(name.as_posix(), b""))
        total = self.total_bytes - previous + before.st_size
        if total > self.maximum_bytes:
            raise PackageScopeError("Source payload budget exceeded; review scope before packaging")
        raw = path.read_bytes()
        after = path.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or len(raw) != before.st_size:
            raise PackageScopeError("Source file changed during packaging")
        self.files[name.as_posix()] = raw
        self.total_bytes = total

def include_linked_evidence(payload, excluded=None, maximum_bytes=MAX_EVIDENCE_BYTES,
                            maximum_files=MAX_EVIDENCE_FILES):
    root = payload.root
    evidence = root / "docs/acceptance"
    excluded = Path(excluded).resolve() if excluded else None
    pending = [name for name in payload.files if name.lower().endswith(".md")]
    visited, selected = set(), {}
    total = 0
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        text = payload.files[name].decode("utf-8")
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = target.strip().split(' "', 1)[0].strip("<>")
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                continue
            path = (root / name).parent / unquote(url.path)
            lexical = Path(os.path.abspath(path))
            if not lexical.is_relative_to(evidence):
                continue
            path = path.resolve()
            if not path.is_relative_to(evidence):
                raise PackageScopeError("Evidence link escapes acceptance root")
            if excluded and path.is_relative_to(excluded):
                continue
            path = lexical
            if path.is_dir():
                indexes = [path / n for n in ["README.md", "index.md", "receipt.json"]]
                path = next((p for p in indexes if p.is_file()), None)
                if path is None:
                    raise PackageScopeError("Evidence directory needs an explicit index or receipt")
            resolved = path.resolve()
            if not resolved.is_relative_to(evidence):
                raise PackageScopeError("Evidence index escapes acceptance root")
            if excluded and resolved.is_relative_to(excluded):
                continue
            if not path.is_file():
                raise PackageScopeError("Referenced acceptance evidence is missing")
            relative = path.relative_to(root).as_posix()
            if relative in selected:
                continue
            size = path.stat().st_size
            if len(selected) >= maximum_files or size > maximum_bytes - total:
                raise PackageScopeError("Linked evidence budget exceeded; retain bulky data separately")
            payload.add(relative, path)
            selected[relative] = len(payload.files[relative])
            total += selected[relative]
            if path.suffix.lower() == ".md":
                pending.append(relative)
    return {"policy": "markdown-reference-closure", "files": len(selected),
            "bytes": total, "maximumBytes": maximum_bytes, "maximumFiles": maximum_files}
