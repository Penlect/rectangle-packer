"""Test anonymous publication, content preservation, and fail-closed privacy checks."""

import io
import tarfile
from pathlib import Path
import tempfile
import unittest

from benchmark.compare import compare_campaigns
from benchmark.privacy import check_public_tree, machine_label, public_source
from benchmark.publish import publish_benchmark
from benchmark.results import load_campaign
from benchmark.storage import sha256_file, write_json

if __package__:
    from .benchmark_fixtures import make_campaign
    from .test_benchmark import _plot_test_campaign
else:
    from benchmark_fixtures import make_campaign
    from test_benchmark import _plot_test_campaign


class TestAnonymousPublication(unittest.TestCase):
    def test_metadata_is_anonymous_and_measurements_are_preserved(self):
        with tempfile.TemporaryDirectory(prefix="TMP_privacy_") as temporary:
            root = Path(temporary)
            manifest, records, cases = make_campaign(root / "private")
            home = "/" + "home/" + "private-user/build"
            manifest.update(
                hostname="private-node",
                container_hostname="private-container",
                output_dir=home,
                environment={"arbitrary_secret": "private note"},
                platform="Linux-custom-private-node-x86_64",
                machine_label="machine-1",
            )
            manifest["build"]["command"] = ["python3", home + "/setup.py"]
            (root / "private/build.log").write_text(
                "gcc -O2 -o " + home + "/output.o\n"
            )
            manifest["build"]["log_sha256"] = sha256_file(root / "private/build.log")
            write_json(root / "private/manifest.json", manifest)
            before = {p.name: p.read_bytes() for p in (root / "private").iterdir()}
            _plot_test_campaign(root / "private", root / "plots")
            public = publish_benchmark(
                root / "private", root / "plots", root / "public"
            )
            checked, measured = load_campaign(root / "public")
            self.assertEqual(measured, records)
            self.assertEqual(
                public["source"]["library_source_sha256"],
                manifest["source"]["library_source_sha256"],
            )
            self.assertEqual(public["timestamp_utc"], "2026-01-01")
            self.assertEqual(public["platform"], "Linux-x86_64")
            self.assertEqual(public["machine_label"], "machine-1")
            self.assertIsNone(public["source"]["git_revision"])
            self.assertIsNone(public["source"]["library_git_revision"])
            self.assertTrue(
                {
                    "hostname",
                    "container_hostname",
                    "output_dir",
                    "environment",
                }.isdisjoint(public)
            )
            self.assertNotIn(home, (root / "public/build.log").read_text())
            check_public_tree(
                root / "public", private_names=("private-node", "private-container")
            )
            self.assertEqual(
                before, {p.name: p.read_bytes() for p in (root / "private").iterdir()}
            )

    def test_unknown_machine_identity_is_not_treated_as_controlled(self):
        with tempfile.TemporaryDirectory(prefix="TMP_privacy_") as temporary:
            root = Path(temporary)
            for name in ("baseline", "candidate"):
                manifest, _, _ = make_campaign(root / name)
                manifest.pop("machine_label")
                write_json(root / name / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "machine_identity"):
                compare_campaigns(
                    root / "baseline", root / "candidate", root / "comparison"
                )

    def test_private_source_path_blocks_publication(self):
        with tempfile.TemporaryDirectory(prefix="TMP_privacy_") as temporary:
            root = Path(temporary)
            (root / "source.txt").write_text("/" + "home/" + "private-user/source")
            with self.assertRaisesRegex(ValueError, "private path"):
                check_public_tree(root)

    def test_machine_labels_are_explicit_public_aliases(self):
        self.assertIsNone(machine_label(None))
        self.assertEqual(machine_label("machine-1"), "machine-1")
        with self.assertRaises(ValueError):
            machine_label("username@host.example")

    def test_archive_headers_are_anonymous_and_library_redaction_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="TMP_privacy_") as temporary:
            root = Path(temporary)
            archive_path = root / "private.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                for name, data in (
                    ("src/example.c", b"int private_symbol;\n"),
                    ("benchmark/example.py", b"# private-node\n"),
                ):
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    member.uid = member.gid = 1234
                    member.uname = member.gname = "private-user"
                    member.mtime = 123456789
                    archive.addfile(member, io.BytesIO(data))
            source = public_source(
                archive_path, root / "public.tar.gz", private_names=("private-node",)
            )
            self.assertEqual(source["redacted_harness_files"], ["benchmark/example.py"])
            with tarfile.open(root / "public.tar.gz") as archive:
                for member in archive.getmembers():
                    self.assertEqual(
                        (
                            member.uid,
                            member.gid,
                            member.uname,
                            member.gname,
                            member.mtime,
                        ),
                        (0, 0, "", "", 0),
                    )
                self.assertEqual(
                    archive.extractfile("src/example.c").read(),
                    b"int private_symbol;\n",
                )
            with self.assertRaisesRegex(ValueError, "measured library"):
                public_source(
                    archive_path,
                    root / "rejected.tar.gz",
                    private_names=("private_symbol",),
                )
