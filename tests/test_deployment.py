"""Phase 7 tests: deployment configuration, environment, security hygiene."""

from __future__ import annotations

import unittest
from pathlib import Path

from qm_training.app import build_workflow
from qm_training.core.config import Settings

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_ENV_KEYS = {
    "AI_PROVIDER",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
}
REQUIRED_PACKAGES = ["python-docx", "pypdf", "python-pptx", "openpyxl", "requests", "Pillow", "lxml"]


class TestEnvFiles(unittest.TestCase):
    def test_env_example_exists_with_keys(self) -> None:
        path = ROOT / ".env.example"
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        for key in REQUIRED_ENV_KEYS:
            self.assertIn(f"{key}=", content)

    def test_env_example_has_no_real_values(self) -> None:
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(("DEEPSEEK_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN")):
                _, _, value = line.partition("=")
                self.assertEqual(value.strip(), "", f"{line} harus kosong di .env.example")

    def test_gitignore_protects_secrets_and_output(self) -> None:
        content = (ROOT / ".gitignore").read_text(encoding="utf-8")
        entries = {line.strip() for line in content.splitlines()}
        for entry in (".env", ".venv/", "output/"):
            self.assertIn(entry, entries)
        self.assertTrue("storage/" in entries or "storage/sessions/" in entries)

    def test_env_file_is_gitignored(self) -> None:
        content = (ROOT / ".gitignore").read_text(encoding="utf-8")
        entries = {line.strip() for line in content.splitlines()}
        self.assertIn(".env", entries, ".env harus di-ignore Git")

    def test_requirements_lists_dependencies(self) -> None:
        content = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        for package in REQUIRED_PACKAGES:
            self.assertIn(package, content)


class TestEnvironment(unittest.TestCase):
    def test_check_environment_report(self) -> None:
        from scripts.check_environment import check_environment

        report = check_environment(ROOT)
        self.assertTrue(report["python_ok"])
        self.assertTrue(report["packages_ok"], report["packages"])
        self.assertIsNotNone(report["libreoffice"])
        self.assertTrue(report["env_example_present"])
        self.assertIn("TELEGRAM_BOT_TOKEN", report["credentials_present"])

    def test_main_check_mode(self) -> None:
        import main as main_module

        self.assertEqual(main_module.main(["--check"]), 0)

    def test_main_without_token_is_pending(self) -> None:
        from unittest import mock

        import main as main_module

        # Hermetic: do not depend on (or start a bot with) real credentials.
        with mock.patch.object(main_module, "Settings") as fake_settings:
            fake_settings.from_env.return_value = Settings(ai_provider="mock", telegram_bot_token=None)
            self.assertEqual(main_module.main([]), 2)

    def test_main_refuses_without_access(self) -> None:
        from unittest import mock

        import main as main_module

        with mock.patch.object(main_module, "Settings") as fake_settings:
            fake_settings.from_env.return_value = Settings(
                ai_provider="mock",
                telegram_bot_token="dummy",
                allowed_user_ids=(),
                owner_user_ids=(),
                allow_open_access=False,
            )
            self.assertEqual(main_module.main([]), 4)


class TestAppWiring(unittest.TestCase):
    def test_build_workflow_mock(self) -> None:
        workflow, is_mock = build_workflow(Settings(ai_provider="mock"))
        self.assertTrue(is_mock)
        self.assertIsNotNone(workflow)


class TestTermuxDocs(unittest.TestCase):
    def test_deployment_doc_marks_termux_pending(self) -> None:
        content = (ROOT / "docs" / "DEPLOYMENT.md").read_text(encoding="utf-8")
        self.assertIn("PENDING_TERMUX_VERIFICATION", content)
        self.assertIn("LibreOffice tidak tersedia native", content)

    def test_termux_script_exists(self) -> None:
        self.assertTrue((ROOT / "scripts" / "termux_setup.sh").exists())


if __name__ == "__main__":
    unittest.main()
