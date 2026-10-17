"""Offline validation of registry release selection and deployment boundaries."""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "deploy_registry_demo.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("deploy_registry_demo", SCRIPT)
registry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registry)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "README.md").write_text("fixture\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "fixture"], cwd=self.repo, check=True)
        self.revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repo).decode().strip()
        self.release_path = self.root / "cache" / "registry-release.json"
        self.download = self.root / "published-release.json"
        self.metadata = {
            "schema_version": 1, "repository": registry.REPOSITORY,
            "image": registry.IMAGE, "platform": "linux/arm64",
            "revision": self.revision, "digest": "sha256:" + "a" * 64,
            "ref": "refs/heads/develop",
            "workflow_run_url": "https://github.com/marianapiccolo/investmind-ai/actions/runs/1234",
        }
        self.download.write_text(json.dumps(self.metadata))
        self.addCleanup(patch.stopall)
        patch.object(registry, "BASE_DIR", self.repo).start()
        patch.object(registry, "RELEASE_PATH", self.release_path).start()
        self.output = io.StringIO()
        patch("sys.stdout", new=self.output).start()

    def test_valid_release_is_cached_privately_and_pinned_by_digest(self):
        release = registry.prepare(self.download)
        self.assertEqual(release["reference"], registry.IMAGE + "@" + self.metadata["digest"])
        self.assertEqual(self.release_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(registry.prepare(), release)

    def test_untrusted_release_fields_are_rejected(self):
        changes = [
            ("image", "ghcr.io/someone/another-project"),
            ("repository", "another/project"),
            ("platform", "linux/amd64"),
            ("ref", "refs/pull/1/merge"),
            ("digest", "sha256:abc; echo unsafe"),
            ("revision", "a" * 39),
            ("revision", ["not-a-string"]),
            ("workflow_run_url", "https://example.invalid/actions/runs/1234"),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError):
                    registry.validate_release({**self.metadata, key: value})

    def test_reference_is_rebuilt_instead_of_trusting_an_extra_field(self):
        result = registry.validate_release({**self.metadata, "reference": "unexpected:latest"})
        self.assertEqual(result["reference"], registry.IMAGE + "@" + self.metadata["digest"])

    def test_actions_artifact_zip_can_be_used_without_extracting_files(self):
        artifact = self.root / "artifact.zip"
        with zipfile.ZipFile(artifact, "w") as archive:
            archive.writestr("published-release.json", json.dumps(self.metadata))
            archive.writestr("../../unexpected.txt", "not extracted")
        result = registry.prepare(artifact)
        self.assertEqual(result["revision"], self.revision)
        self.assertFalse((self.root / "unexpected.txt").exists())

    def test_oversized_metadata_is_rejected(self):
        self.download.write_text(" " * 16385)
        with self.assertRaisesRegex(ValueError, "size"):
            registry.prepare(self.download)

    def test_a_different_commit_does_not_replace_selected_release(self):
        registry.prepare(self.download)
        original = self.release_path.read_bytes()
        self.download.write_text(json.dumps({**self.metadata, "revision": "b" * 40}))
        with self.assertRaisesRegex(RuntimeError, "checkout must match"):
            registry.prepare(self.download)
        self.assertEqual(self.release_path.read_bytes(), original)

    def test_dirty_tracked_files_block_release_preparation(self):
        (self.repo / "README.md").write_text("uncommitted change\n")
        with self.assertRaises(subprocess.CalledProcessError):
            registry.prepare(self.download)
        self.assertFalse(self.release_path.exists())

    def test_prepare_only_does_not_access_aws_ssh_or_request_a_token(self):
        with patch.object(sys, "argv", ["deploy_registry_demo.py", str(self.download), "--prepare-only"]), \
             patch.object(registry, "find_source") as aws, patch.object(registry, "ssh") as ssh, \
             patch.object(registry.getpass, "getpass") as prompt:
            self.assertEqual(registry.main(), 0)
            aws.assert_not_called()
            ssh.assert_not_called()
            prompt.assert_not_called()

    def setup_deployment(self, *, host="3.219.31.113"):
        inventory = self.root / "inventory.json"
        inventory.write_text(json.dumps({"all": {"children": {"investmind": {"hosts": {
            "investmind_demo": {
                "ansible_host": host, "ansible_user": "ubuntu",
                "ansible_ssh_common_args": "-o StrictHostKeyChecking=yes -o IdentitiesOnly=yes",
                "ansible_ssh_private_key_file": str(Path.home() / ".ssh" / "investmind_demo"),
            }
        }}}}}))
        executable = self.root / "ansible-playbook"
        executable.write_text("fixture")
        patch.object(registry, "INVENTORY_PATH", inventory).start()
        patch.object(registry, "ANSIBLE", executable).start()
        patch.object(registry, "find_source", return_value=("i-0123456789abcdef0", "3.219.31.113")).start()

    def test_stale_inventory_is_rejected_before_requesting_token(self):
        self.setup_deployment(host="98.92.64.115")
        with patch.object(registry.getpass, "getpass") as prompt, patch.object(registry, "ssh") as ssh:
            with self.assertRaisesRegex(RuntimeError, "Refresh the Ansible inventory"):
                registry.deploy()
            prompt.assert_not_called()
            ssh.assert_not_called()

    def test_host_key_failure_stops_before_requesting_token(self):
        self.setup_deployment()
        with patch.object(registry, "ssh", side_effect=subprocess.CalledProcessError(255, ["ssh"])), \
             patch.object(registry.getpass, "getpass") as prompt:
            with self.assertRaises(subprocess.CalledProcessError):
                registry.deploy()
            prompt.assert_not_called()

    def test_token_only_reaches_the_ansible_child_environment(self):
        self.setup_deployment()
        secret = "fixture-token-not-a-real-credential"
        seen = {}
        def run(args, **kwargs):
            seen["args"] = args
            seen["environment"] = kwargs["env"]
            self.assertEqual(kwargs["env"]["INVESTMIND_GHCR_TOKEN"], secret)
            return subprocess.CompletedProcess(args, 0)
        with patch.object(registry, "ssh"), patch.object(registry.getpass, "getpass", return_value=secret), \
             patch.object(registry.subprocess, "run", side_effect=run):
            registry.deploy()
        self.assertNotIn(secret, " ".join(seen["args"]))
        self.assertNotIn(secret, self.output.getvalue())
        self.assertNotIn("INVESTMIND_GHCR_TOKEN", seen["environment"])
        self.assertNotEqual(os.environ.get("INVESTMIND_GHCR_TOKEN"), secret)

    def test_token_is_removed_from_child_environment_after_a_failure(self):
        self.setup_deployment()
        environment = {}
        def failed(args, **kwargs):
            environment["child"] = kwargs["env"]
            raise subprocess.CalledProcessError(2, args)
        with patch.object(registry, "ssh"), patch.object(registry.getpass, "getpass", return_value="fixture-token"), \
             patch.object(registry.subprocess, "run", side_effect=failed):
            with self.assertRaises(subprocess.CalledProcessError):
                registry.deploy()
        self.assertNotIn("INVESTMIND_GHCR_TOKEN", environment["child"])


if __name__ == "__main__":
    unittest.main()
