import sys
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collector import codex_executable, parse_codex_limits


class CodexUsageTests(unittest.TestCase):
    def test_weekly_only_account(self):
        response = {"rateLimitsByLimitId": {
            "codex_other": {"limitId": "codex_other", "primary": {"usedPercent": 91, "windowDurationMins": 300}},
            "codex": {"limitId": "codex", "primary": {
                "usedPercent": 62, "windowDurationMins": 10080, "resetsAt": 1990000000}}}}
        result = parse_codex_limits(response)
        self.assertIsNone(result["five_hour"])
        self.assertEqual(result["seven_day"], {"used": 62, "reset": 1990000000})

    def test_legacy_single_bucket_with_two_windows(self):
        response = {"rateLimits": {"limitId": "codex",
            "primary": {"usedPercent": 15.4, "windowDurationMins": 300, "resetsAt": 1990000000},
            "secondary": {"usedPercent": 48, "windowDurationMins": 10080, "resetsAt": 1990000000}}}
        result = parse_codex_limits(response)
        self.assertEqual(result["five_hour"]["used"], 15.4)
        self.assertEqual(result["seven_day"]["used"], 48)

    def test_missing_usage(self):
        self.assertIsNone(parse_codex_limits({"rateLimits": {"limitId": "codex", "primary": None}}))

    def test_stale_configured_cli_uses_updated_desktop_cli(self):
        with tempfile.TemporaryDirectory() as root:
            current = Path(root) / "OpenAI" / "Codex" / "bin" / "new-version" / "codex.exe"
            current.parent.mkdir(parents=True)
            current.touch()
            with patch.dict(os.environ, {"CODEX_CLI_PATH": str(Path(root) / "old-version" / "codex.exe"),
                                      "LOCALAPPDATA": root}):
                with patch("collector.shutil.which", return_value=None):
                    self.assertEqual(codex_executable(), str(current))


if __name__ == "__main__":
    unittest.main()
