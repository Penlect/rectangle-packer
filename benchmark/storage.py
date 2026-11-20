"""Small filesystem primitives for immutable campaigns and atomic status updates."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    """Replace a status file only after its complete new contents are written."""
    descriptor, temporary = tempfile.mkstemp(prefix="TMP_", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def new_directory(destination: Path):
    """Publish a staged directory, refusing even an existing empty destination."""
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    reserved = destination.stat()
    staging = Path(tempfile.mkdtemp(prefix="TMP_", dir=destination.parent))
    try:
        yield staging
        current = destination.stat()
        if (current.st_dev, current.st_ino) != (
            reserved.st_dev,
            reserved.st_ino,
        ) or any(destination.iterdir()):
            raise FileExistsError("publication destination changed while staging")
        if os.name == "nt":
            # Windows cannot replace an existing directory. Its rename refuses
            # any newly created destination, so releasing our reservation first
            # still cannot overwrite another publisher's directory.
            destination.rmdir()
            staging.rename(destination)
        else:
            os.replace(staging, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if destination.exists():
            current = destination.stat()
            if (current.st_dev, current.st_ino) == (reserved.st_dev, reserved.st_ino):
                try:
                    destination.rmdir()
                except OSError:
                    pass
