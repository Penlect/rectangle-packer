"""Export buildable sources and identify the exact sources and native artifact used."""

from __future__ import annotations

import gzip
import hashlib
from importlib import metadata
import io
import json
import os
import shlex
import shutil
from pathlib import Path
import subprocess
import sys
import sysconfig
import tarfile

from benchmark.corpus import canonical
from benchmark.storage import new_directory, sha256_file, write_json

ROOT = Path(__file__).resolve().parents[1]


def compiler_identity() -> dict:
    """Record the configured compiler command and its reported version when available."""
    command = shlex.split(os.environ.get("CC") or sysconfig.get_config_var("CC") or "")
    version = None
    if command:
        try:
            result = subprocess.run(
                [*command, "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return {"command": command, "version": version}


def require_build_sources(root: Path = ROOT) -> None:
    if not all(
        (root / name).is_file()
        for name in ("setup.py", "pyproject.toml", "rpack/_core.pyx", "src/rpackcore.c")
    ):
        raise ValueError(
            "this command requires a rectangle-packer source checkout or exported source tree"
        )


def _library_file(name: str) -> bool:
    return name.startswith(("rpack/", "src/", "include/")) or name in (
        "setup.py",
        "pyproject.toml",
    )


def source_files(root: Path = ROOT) -> dict[str, str]:
    paths = set()
    for pattern in (
        "rpack/*.py",
        "rpack/*.pyx",
        "rpack/*.pxd",
        "src/*.c",
        "include/*.h",
        "benchmark/*.py",
        "test/*.py",
    ):
        paths.update(root.glob(pattern))
    for name in (
        "setup.py",
        "pyproject.toml",
        "Makefile",
        "MANIFEST.in",
        "README-pypi.rst",
        "LICENSE.md",
        "benchmark/Dockerfile",
        ".dockerignore",
    ):
        if (root / name).is_file():
            paths.add(root / name)
    return {
        path.relative_to(root).as_posix(): sha256_file(path) for path in sorted(paths)
    }


def identify_source(root: Path = ROOT) -> dict:
    files = source_files(root)
    digest = hashlib.sha256(canonical(files)).hexdigest()
    revision = None
    dirty = None
    try:
        toplevel = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if Path(toplevel).resolve() == root.resolve():
            revision = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
            ).strip()
            dirty = bool(
                subprocess.check_output(
                    [
                        "git",
                        "-C",
                        str(root),
                        "status",
                        "--porcelain",
                        "--untracked-files=normal",
                    ],
                    text=True,
                ).strip()
            )
    except (OSError, subprocess.CalledProcessError):
        pass
    library_revision = harness_revision = revision
    exported = root / "benchmark-source.json"
    if revision is None and exported.exists():
        origin = json.loads(exported.read_text())
        revision = origin.get("git_revision")
        dirty = origin.get("git_dirty")
        library_revision = origin.get("library_git_revision", revision)
        harness_revision = origin.get("harness_git_revision", revision)
        if files != origin.get("files") or digest != origin.get("source_sha256"):
            dirty = True
    library_files = {
        name: digest for name, digest in files.items() if _library_file(name)
    }
    return {
        "git_revision": revision,
        "git_dirty": dirty,
        "library_git_revision": library_revision,
        "harness_git_revision": harness_revision,
        "library_source_sha256": hashlib.sha256(canonical(library_files)).hexdigest(),
        "source_sha256": digest,
        "files": files,
    }


def source_archive(destination: Path, source: dict, root: Path = ROOT) -> None:
    with destination.open("xb") as output:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=output, mtime=0
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as archive:
                for filename, expected in source["files"].items():
                    data = (root / filename).read_bytes()
                    if hashlib.sha256(data).hexdigest() != expected:
                        raise ValueError("source changed while creating snapshot")
                    info = tarfile.TarInfo(filename)
                    info.size = len(data)
                    info.mode = 0o644
                    archive.addfile(info, io.BytesIO(data))
                data = canonical(source) + b"\n"
                info = tarfile.TarInfo("benchmark-source.json")
                info.size = len(data)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(data))


def export_sources(
    destination: Path, root: Path = ROOT, library_ref: str | None = None
) -> dict:
    """Create a clean build directory with verifiable revision metadata."""
    require_build_sources(root)
    source = identify_source(root)
    library_revision = None
    if library_ref is not None:
        library_revision = subprocess.check_output(
            [
                "git",
                "-C",
                str(root),
                "rev-parse",
                "--verify",
                "--end-of-options",
                library_ref + "^{commit}",
            ],
            text=True,
        ).strip()
    with new_directory(destination) as staging:
        for filename, digest in source["files"].items():
            data = (root / filename).read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("source changed during export")
            target = staging / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if library_revision is not None:
            for filename in source["files"]:
                if _library_file(filename):
                    (staging / filename).unlink()
            names = subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(root),
                    "ls-tree",
                    "-r",
                    "--name-only",
                    library_revision,
                ],
                text=True,
            ).splitlines()
            for name in names:
                if _library_file(name):
                    path = staging / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(
                        subprocess.check_output(
                            [
                                "git",
                                "-C",
                                str(root),
                                "show",
                                f"{library_revision}:{name}",
                            ]
                        )
                    )
            combined = identify_source(staging)
            combined.update(
                git_revision=None,
                git_dirty=source["git_dirty"],
                library_git_revision=library_revision,
                harness_git_revision=source["harness_git_revision"],
            )
            source = combined
        write_json(staging / "benchmark-source.json", source)
    return source


def build_extension(log_path: Path, root: Path = ROOT) -> dict:
    """Force a fresh build and retain the actual compiler commands and diagnostics."""
    require_build_sources(root)
    runtime = log_path.parent / "runtime"
    command = [
        sys.executable,
        "setup.py",
        "build_ext",
        "--force",
        "--build-lib",
        str(runtime),
        "--build-temp",
        str(log_path.parent / "build-temp"),
    ]
    with log_path.open("x", encoding="utf-8") as log:
        subprocess.run(
            command,
            cwd=root,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    for path in (root / "rpack").glob("*.py"):
        shutil.copyfile(path, runtime / "rpack" / path.name)
    versions = {}
    for name in ("Cython", "setuptools"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "command": command,
        "compiler": compiler_identity(),
        "package_versions": versions,
        "environment": {
            key: os.environ.get(key)
            for key in ("CC", "CFLAGS", "CPPFLAGS", "LDFLAGS", "LDSHARED", "ARCHFLAGS")
        },
        "log_file": log_path.name,
        "log_sha256": sha256_file(log_path),
    }
