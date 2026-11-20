"""Create anonymous public metadata and source archives without changing measurements.

Private run directories remain untouched. Public snapshots are content-addressed;
redaction of harness text is recorded, and changes to measured library files are
rejected. Source and input contents still need their owner's publication review.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

from benchmark.corpus import canonical
from benchmark.provenance import _library_file
from benchmark.storage import sha256_file

# Only documented measurement metadata crosses the publication boundary.
PUBLIC_FIELDS = frozenset(
    """algorithms benchmark_schema_version build_seconds build_environment
completed_job_count containerized count_sweep_instances count_sweep_scale
count_sweep_values cpu_governors cpu_model duration_seconds expected_job_count
extension_filename extension_sha256 finished_timestamp_utc job_grid_sha256
job_order_seed max_repeat measurement_mode measurement_seconds package_versions
pathology_baseline_instances pathology_baseline_scale pathology_heights
pathology_repeats platform profile python_compiler python_version results_compression
results_file results_sha256 results_uncompressed_sha256 rpack_version
scale_sweep_base_scale scale_sweep_instances scale_sweep_n scale_sweep_values
status structured_max_n structured_repeats target_time_ns timestamp_utc
worker_cpus workers timing_blocks timeout_seconds outcomes corpus_file
corpus_file_sha256 corpus_sha256""".split()
)
PERSONAL_PATH = re.compile(
    r"/(?:home|Users)/[^\s\"\'<>]+|[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\s\"\'<>]+"
)
PRIVATE_IP = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
)
CREDENTIAL = re.compile(
    r"-----BEGIN (?:OPENSSH|RSA|EC|DSA|PRIVATE).*KEY-----|\bgh[pousr]_[A-Za-z0-9]{20,}|\bsk-[A-Za-z0-9]{24,}"
)
ABSOLUTE_PATH = re.compile(
    r"(?<![\w:/])/(?!/)[^\s\"\'<>;,\)\]\}]+|[A-Za-z]:[\\/][^\s\"\'<>;,\)\]\}]+"
)


def machine_label(value):
    if value is not None and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", value):
        raise ValueError(
            "machine label must be 1–48 lowercase letters, digits or hyphens"
        )
    return value


def check_text(text, *, private_names=()):
    if PERSONAL_PATH.search(text) or PRIVATE_IP.search(text) or CREDENTIAL.search(text):
        raise ValueError(
            "publication contains a private path, network address or credential marker"
        )
    for name in private_names:
        if name and re.search(re.escape(name), text, re.IGNORECASE):
            raise ValueError("publication contains an identifying machine name")


def public_text(text, *, private_names=(), paths=False):
    for name in sorted(set(private_names), key=len, reverse=True):
        if name:
            text = re.sub(
                re.escape(name), "anonymous-machine", text, flags=re.IGNORECASE
            )
    if paths:
        text = ABSOLUTE_PATH.sub("<path>", text)
        text = PRIVATE_IP.sub("<network-address>", text)
    check_text(text, private_names=private_names)
    return text


def _public_value(value, private_names):
    if isinstance(value, str):
        return public_text(value, private_names=private_names, paths=True)
    if isinstance(value, list):
        return [_public_value(item, private_names) for item in value]
    if isinstance(value, dict):
        return {key: _public_value(item, private_names) for key, item in value.items()}
    return value


def public_source(archive_path, destination, *, private_names=()):
    """Repack sources with anonymous tar headers and independently verified hashes."""
    files = {}
    original = None
    changed = []
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            name = member.name
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError(
                    "source archive must contain only relative regular files"
                )
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError(
                    "source archive must not contain links or special files"
                )
            if name in files:
                raise ValueError("duplicate source archive member")
            data = archive.extractfile(member).read()
            if name == "benchmark-source.json":
                original = json.loads(data)
                continue
            check_text(name, private_names=private_names)
            text = data.decode("utf-8")
            clean = public_text(text, private_names=private_names).encode("utf-8")
            if clean != data:
                if _library_file(name):
                    raise ValueError("redaction would alter measured library sources")
                changed.append(name)
            files[name] = clean
    digests = {
        name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
    }
    library = {name: digest for name, digest in digests.items() if _library_file(name)}
    library_digest = hashlib.sha256(canonical(library)).hexdigest()
    if original is not None and library_digest != original["library_source_sha256"]:
        raise ValueError("public library identity differs from measured library")
    source = {
        "git_revision": None,
        "git_dirty": None,
        "library_git_revision": None,
        "harness_git_revision": None,
        "library_source_sha256": library_digest,
        "source_sha256": hashlib.sha256(canonical(digests)).hexdigest(),
        "files": digests,
        "publication_privacy_version": 1,
        "redacted_harness_files": sorted(
            set(changed + (original or {}).get("redacted_harness_files", []))
        ),
    }
    files["benchmark-source.json"] = canonical(source) + b"\n"
    with destination.open("xb") as stream:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=stream, mtime=0
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as archive:
                for name, data in sorted(files.items()):
                    info = tarfile.TarInfo(name)
                    info.size, info.mode = len(data), 0o644
                    archive.addfile(info, io.BytesIO(data))
    return source


def public_manifest(manifest, input_dir, staging):
    """Strip run identity, normalize paths, and bind the sanitized evidence."""
    private_names = tuple(
        str(manifest[key])
        for key in ("hostname", "container_hostname")
        if manifest.get(key)
    )
    private_names += tuple(
        re.sub(r"(?<=[A-Za-z])(?=\d)", " ", name) for name in private_names
    )
    public = {
        key: copy.deepcopy(value)
        for key, value in manifest.items()
        if key in PUBLIC_FIELDS
    }
    public = _public_value(public, private_names)
    public["machine_label"] = machine_label(manifest.get("machine_label"))
    public["publication_privacy_version"] = 1
    for key in ("timestamp_utc", "finished_timestamp_utc"):
        if key in public:
            public[key] = public[key][:10]
    # Kernel/build strings can contain private build-host names. Keep OS and ISA.
    platform = str(manifest.get("platform", "unknown"))
    system = platform.split("-")[0]
    architecture = next(
        (a for a in ("x86_64", "aarch64", "arm64", "AMD64", "i686") if a in platform),
        "unspecified",
    )
    public["platform"] = system + "-" + architecture
    if (input_dir / "source.tar.gz").exists():
        public["source"] = public_source(
            input_dir / "source.tar.gz",
            staging / "source.tar.gz",
            private_names=private_names,
        )
        public["source_archive_sha256"] = sha256_file(staging / "source.tar.gz")
    build = manifest.get("build")
    if build is not None:
        public["build"] = _public_value(
            {
                key: build[key]
                for key in (
                    "command",
                    "compiler",
                    "environment",
                    "package_versions",
                    "log_file",
                )
                if key in build
            },
            private_names,
        )
        clean_log = public_text(
            (input_dir / "build.log").read_text(),
            private_names=private_names,
            paths=True,
        )
        (staging / "build.log").write_text(clean_log)
        public["build"]["log_sha256"] = sha256_file(staging / "build.log")
    return public, private_names


def check_public_tree(directory, *, private_names=()):
    """Fail closed on recognizable private content, including archive members."""
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        check_text(path.relative_to(directory).as_posix(), private_names=private_names)
        if path.name.endswith(".tar.gz"):
            with tarfile.open(path) as archive:
                for member in archive.getmembers():
                    check_text(member.name, private_names=private_names)
                    if member.isfile():
                        check_text(
                            archive.extractfile(member).read().decode("utf-8"),
                            private_names=private_names,
                        )
        else:
            data = (
                gzip.decompress(path.read_bytes())
                if path.suffix == ".gz"
                else path.read_bytes()
            )
            check_text(data.decode("utf-8"), private_names=private_names)
