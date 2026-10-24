"""Offline orchestration tests. Real PostgreSQL restoration is tested by 'verify'."""

import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "demo_database_backup.py"
SPEC = importlib.util.spec_from_file_location("demo_database_backup", SCRIPT)
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.backups = self.root / "backups"
        self.addCleanup(patch.stopall)
        patch.object(demo, "BACKUP_DIR", self.backups).start()
        patch("sys.stdout", new=io.StringIO()).start()

    def source(self):
        patch.object(demo, "find_source", return_value=("i-0123456789abcdef0", "98.92.64.115")).start()

    def simulate_ssh(self, *, failure=False, payload=b"PGDMP" + b"test-archive" * 10):
        def ssh(address, args, **kwargs):
            if args[:3] == ["sudo", "-n", "readlink"]:
                return subprocess.CompletedProcess(args, 0, ("/opt/investmind/releases/" + "a" * 40).encode(), b"")
            if "SHOW server_version_num" in args[-1]:
                return subprocess.CompletedProcess(args, 0, b"180003\n", b"")
            self.assertIn("--format=custom", args[-1])
            self.assertIn("exec pg_dump", args[-1])
            kwargs["stdout"].write(payload)
            if failure:
                raise subprocess.CalledProcessError(1, args, stderr=b"export failed")
            return subprocess.CompletedProcess(args, 0, None, b"")
        return ssh

    def make_archive(self):
        self.source()
        with patch.object(demo, "ssh", side_effect=self.simulate_ssh()):
            return demo.backup()

    def test_backup_private_files_and_manifest(self):
        archive = self.make_archive()
        metadata = json.loads((archive.parent / "metadata.json").read_text())
        self.assertEqual(metadata["sha256"], demo.sha256(archive))
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
        self.assertEqual(archive.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual((archive.parent / "metadata.json").stat().st_mode & 0o777, 0o600)
        self.assertFalse((archive.parent / "verification.json").exists())
        self.assertNotIn("password", metadata)

    def test_interrupted_export_removes_partial_backup(self):
        self.source()
        with patch.object(demo, "ssh", side_effect=self.simulate_ssh(failure=True)):
            with self.assertRaises(subprocess.CalledProcessError):
                demo.backup()
        self.assertEqual(list(self.backups.iterdir()), [])

    def test_invalid_archive_is_not_published(self):
        self.source()
        with patch.object(demo, "ssh", side_effect=self.simulate_ssh(payload=b"error page")):
            with self.assertRaisesRegex(RuntimeError, "custom-format"):
                demo.backup()
        self.assertEqual(list(self.backups.iterdir()), [])

    def test_wrong_account_stops_before_terraform_or_ssh(self):
        with patch.object(demo, "aws_json", return_value={"Account": "225989374671"}), \
             patch.object(demo, "read_text") as read, patch.object(demo, "ssh") as ssh:
            with self.assertRaisesRegex(RuntimeError, "Unexpected AWS account"):
                demo.find_source()
            read.assert_not_called()
            ssh.assert_not_called()

    def test_wrong_instance_tags_are_rejected(self):
        identity = {"Account": demo.EXPECTED_ACCOUNT}
        instance = {"Reservations": [{"Instances": [{
            "InstanceId": "i-0123456789abcdef0", "VpcId": "vpc-demo",
            "KeyName": "investmind-demo", "State": {"Name": "running"},
            "PublicIpAddress": "98.92.64.115", "Tags": [],
        }]}]}
        outputs = {"instance_id": {"value": "i-0123456789abcdef0"}, "vpc_id": {"value": "vpc-demo"}}
        with patch.object(demo, "aws_json", side_effect=[identity, instance]), \
             patch.object(demo, "read_text", return_value=json.dumps(outputs)):
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                demo.find_source()

    def test_checksum_failure_does_not_start_docker(self):
        archive = self.make_archive()
        archive.write_bytes(archive.read_bytes() + b"corruption")
        with patch.object(demo, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                demo.verify(str(archive))
            run.assert_not_called()

    def test_same_size_corruption_is_detected(self):
        archive = self.make_archive()
        original = archive.read_bytes()
        archive.write_bytes(original[:-1] + b"X")
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            demo.verify(str(archive))

    def simulate_docker(self, calls, *, fail_restore=False, missing_vector=False):
        def run(args, **kwargs):
            calls.append(args)
            output = b""
            if args[1:3] == ["image", "inspect"]:
                output = ("sha256:" + "b" * 64).encode()
            elif args[1] == "create":
                output = ("c" * 64).encode()
            elif "pg_restore" in args:
                self.assertIsNotNone(kwargs.get("stdin"))
                if fail_restore:
                    raise subprocess.CalledProcessError(1, args, stderr=b"invalid dump")
            elif "psql" in args:
                output = json.dumps({"vector_version": None if missing_vector else "0.8.7",
                                     "migrations": 30, "assets": 1, "transactions": 2}).encode()
            return subprocess.CompletedProcess(args, 0, output, b"")
        return run

    def test_restore_is_isolated_and_cleaned_up(self):
        archive = self.make_archive()
        original = archive.read_bytes()
        calls = []
        with patch.object(demo, "run", side_effect=self.simulate_docker(calls)), \
             patch.object(demo, "aws_json") as aws, patch.object(demo, "ssh") as ssh:
            report = demo.verify("latest")
            aws.assert_not_called()
            ssh.assert_not_called()
        create = next(args for args in calls if args[1] == "create")
        self.assertEqual(create[create.index("--network") + 1], "none")
        self.assertNotIn("--publish", create)
        self.assertNotIn("--volume", create)
        self.assertEqual(calls[-1], ["docker", "rm", "--force", "--volumes", "c" * 64])
        restore = next(args for args in calls if "pg_restore" in args)
        self.assertIn("--single-transaction", restore)
        self.assertNotIn("--clean", restore)
        self.assertEqual(report["restored_counts"]["assets"], 1)
        self.assertEqual(archive.read_bytes(), original)
        self.assertTrue((archive.parent / "verification.json").is_file())

    def test_failed_restore_cleans_up_without_success_report(self):
        archive = self.make_archive()
        calls = []
        with patch.object(demo, "run", side_effect=self.simulate_docker(calls, fail_restore=True)):
            with self.assertRaises(subprocess.CalledProcessError):
                demo.verify(str(archive))
        self.assertEqual(calls[-1][1:4], ["rm", "--force", "--volumes"])
        self.assertTrue(archive.exists())
        self.assertFalse((archive.parent / "verification.json").exists())

    def test_missing_vector_extension_is_not_a_success(self):
        archive = self.make_archive()
        calls = []
        with patch.object(demo, "run", side_effect=self.simulate_docker(calls, missing_vector=True)):
            with self.assertRaisesRegex(RuntimeError, "vector extension"):
                demo.verify(str(archive))
        self.assertFalse((archive.parent / "verification.json").exists())

    def test_latest_with_no_backups(self):
        with self.assertRaisesRegex(RuntimeError, "No backup found"):
            demo.resolve_archive("latest")


if __name__ == "__main__":
    unittest.main()
