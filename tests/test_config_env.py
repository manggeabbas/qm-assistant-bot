"""Regression tests for .env loading and configuration precedence."""

from __future__ import annotations

import contextlib
import os
import unittest
from pathlib import Path

from qm_training.core.config import (
    DEFAULT_ENV_PATH,
    PROJECT_ROOT,
    env_file_status,
    load_dotenv,
    resolve_env_path,
)

KEYS = ("DEEPSEEK_API_KEY", "TELEGRAM_BOT_TOKEN", "GEMINI_API_KEY", "OPENAI_API_KEY", "AI_MODEL")


@contextlib.contextmanager
def clean_env(keys=KEYS):
    saved = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ.pop(key, None)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def write_env(path: Path, text: str, bom: bool = False) -> Path:
    data = text.encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)
    return path


class TestLoadDotenv(unittest.TestCase):
    def test_default_path_is_project_root_env(self) -> None:
        # Regression: config.py must use the real project root, not qm_training/.
        self.assertEqual(DEFAULT_ENV_PATH.name, ".env")
        self.assertEqual(DEFAULT_ENV_PATH, PROJECT_ROOT / ".env")
        self.assertTrue(DEFAULT_ENV_PATH.is_absolute())
        self.assertTrue((PROJECT_ROOT / "AGENTS.md").exists(), "PROJECT_ROOT bukan root project")
        self.assertTrue((PROJECT_ROOT / "qm_training").is_dir())
        self.assertEqual(resolve_env_path(), DEFAULT_ENV_PATH)
        self.assertNotEqual(DEFAULT_ENV_PATH.parent.name, "qm_training")

    def test_sets_missing_key(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp, clean_env():
            env = write_env(Path(tmp) / ".env", "DEEPSEEK_API_KEY=abc\n")
            load_dotenv(env)
            self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "abc")

    def test_does_not_override_non_empty_env(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp, clean_env():
            os.environ["DEEPSEEK_API_KEY"] = "from_real_env"
            env = write_env(Path(tmp) / ".env", "DEEPSEEK_API_KEY=from_dotenv\n")
            load_dotenv(env)
            self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "from_real_env")

    def test_fills_empty_env_from_dotenv(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp, clean_env():
            os.environ["DEEPSEEK_API_KEY"] = ""  # empty export must not shadow .env
            env = write_env(Path(tmp) / ".env", "DEEPSEEK_API_KEY=from_dotenv\n")
            load_dotenv(env)
            self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "from_dotenv")

    def test_handles_export_quotes_bom_crlf(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp, clean_env():
            env = write_env(
                Path(tmp) / ".env",
                'export DEEPSEEK_API_KEY="hello world"\r\nTELEGRAM_BOT_TOKEN=\'tok\'\r\n# comment\r\n',
                bom=True,
            )
            load_dotenv(env)
            self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "hello world")
            self.assertEqual(os.environ["TELEGRAM_BOT_TOKEN"], "tok")

    def test_missing_file_is_noop(self) -> None:
        with tempfile_dir() as tmp, clean_env():
            load_dotenv(Path(tmp) / "nope.env")
            self.assertNotIn("DEEPSEEK_API_KEY", os.environ)


def tempfile_dir():
    import tempfile

    return tempfile.TemporaryDirectory()


class TestSafeDiagnostics(unittest.TestCase):
    def test_env_file_status_never_exposes_values(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            env = write_env(
                Path(tmp) / ".env",
                "DEEPSEEK_API_KEY=super-secret\nGEMINI_API_KEY=\n",
            )
            status = env_file_status(env)
            self.assertTrue(status["exists"])
            self.assertEqual(status["keys"]["DEEPSEEK_API_KEY"], "non-empty")
            self.assertEqual(status["keys"]["GEMINI_API_KEY"], "empty")
            self.assertNotIn("super-secret", repr(status))


class TestCheckEnvironmentLoadsDotenv(unittest.TestCase):
    def test_check_environment_reflects_env_file(self) -> None:
        import tempfile

        from scripts.check_environment import check_environment

        with tempfile.TemporaryDirectory() as tmp, clean_env():
            root = Path(tmp)
            write_env(
                root / ".env",
                "DEEPSEEK_API_KEY=secret-value\nTELEGRAM_BOT_TOKEN=token-value\nGEMINI_API_KEY=\n",
            )
            report = check_environment(root)
            self.assertTrue(report["credentials_present"]["DEEPSEEK_API_KEY"])
            self.assertTrue(report["credentials_present"]["TELEGRAM_BOT_TOKEN"])
            self.assertFalse(report["credentials_present"]["GEMINI_API_KEY"])
            self.assertNotIn("secret-value", repr(report))
            self.assertNotIn("token-value", repr(report))


if __name__ == "__main__":
    unittest.main()
