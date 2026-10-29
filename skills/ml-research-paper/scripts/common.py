"""Small standard-library helpers shared by project tools (Python 3.10+)."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def inside(root, relative):
    """Resolve a project-relative path and reject traversal/symlink escape."""
    root = Path(root).resolve()
    if Path(relative).is_absolute():
        raise ValueError("Expected a relative path: " + str(relative))
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Path escapes project: " + str(relative))
    return target


def inventory(root, names):
    result = {}
    for name in names:
        path = inside(root, name)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Missing or empty evidence: " + str(name))
        result[path.relative_to(Path(root).resolve()).as_posix()] = digest(path)
    if not result:
        raise ValueError("At least one evidence file is required")
    return result


class ProjectLock:
    """Fail closed on concurrent/interrupted writers; never silently break locks."""
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(self.fd, json.dumps({"pid": os.getpid(), "time": now()}).encode())
        return self

    def __exit__(self, *unused):
        os.close(self.fd)
        self.path.unlink()
