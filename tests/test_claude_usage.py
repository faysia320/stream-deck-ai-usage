import io
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collector


def http_error(code, headers=None):
    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    return urllib.error.HTTPError(collector.CLAUDE_USAGE_URL, code, "error", message, io.BytesIO(b""))


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ClaudeUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            patch.object(collector, "DATA", root / "data"),
            patch.object(collector, "CLAUDE", root / "data" / "claude.json"),
            patch.object(collector, "CLAUDE_API_STATE", root / "data" / "claude_api.json"),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(root)}),
            patch.object(collector, "latest_codex", return_value=None),
        ]
        for item in self.patches:
            item.start()
        self.credentials = root / ".credentials.json"
        self.write_token(expires=(time.time() + 3600) * 1000)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def write_token(self, expires):
        self.credentials.write_text(json.dumps({"claudeAiOauth": {
            "accessToken": "token", "refreshToken": "refresh", "expiresAt": expires}}))

    def write_statusline(self):
        collector.write_json(collector.CLAUDE, {"updated": int(time.time()),
                                                "five_hour": {"used": 5, "reset": 1990000000},
                                                "seven_day": None})

    def test_parse_usage_response(self):
        result = collector.parse_claude_usage({
            "five_hour": {"utilization": 37.0, "resets_at": "2033-01-21T05:00:00.000000+00:00"},
            "seven_day": {"utilization": 120, "resets_at": None},
            "seven_day_opus": None})
        self.assertEqual(result["five_hour"], {"used": 37.0, "reset": 1989896400})
        self.assertEqual(result["seven_day"], {"used": 100, "reset": None})

    def test_missing_windows(self):
        self.assertIsNone(collector.parse_claude_usage({"five_hour": None}))

    def test_api_result_is_shared_with_statusline_file(self):
        body = json.dumps({"five_hour": {"utilization": 20, "resets_at": 1990000000}}).encode()
        with patch("collector.urllib.request.urlopen", return_value=Response(body)) as urlopen:
            result = collector.collect()["claude"]
        self.assertEqual(result["five_hour"]["used"], 20)
        self.assertEqual(urlopen.call_args.args[0].get_header("Authorization"), "Bearer token")
        self.assertEqual(json.loads(collector.CLAUDE.read_text())["five_hour"]["used"], 20)

    def test_expired_token_is_not_refreshed(self):
        self.write_token(expires=(time.time() - 10) * 1000)
        self.write_statusline()
        with patch("collector.urllib.request.urlopen") as urlopen:
            result = collector.collect()["claude"]
        urlopen.assert_not_called()
        self.assertEqual(result["five_hour"]["used"], 5)
        self.assertIn('"refresh"', self.credentials.read_text())

    def test_unauthorized_falls_back_and_backs_off(self):
        self.write_statusline()
        with patch("collector.urllib.request.urlopen", side_effect=http_error(401)) as urlopen:
            self.assertEqual(collector.collect()["claude"]["five_hour"]["used"], 5)
            collector.collect()
        self.assertEqual(urlopen.call_count, 1)

    def test_rate_limit_respects_retry_after(self):
        with patch("collector.urllib.request.urlopen", side_effect=http_error(429, {"Retry-After": "120"})):
            self.assertIsNone(collector.latest_claude_api())
        state = json.loads(collector.CLAUDE_API_STATE.read_text())
        self.assertAlmostEqual(state["next"], time.time() + 120, delta=5)

    def test_network_error_falls_back(self):
        self.write_statusline()
        with patch("collector.urllib.request.urlopen", side_effect=TimeoutError()):
            self.assertEqual(collector.collect()["claude"]["five_hour"]["used"], 5)

    def test_disabled_by_installer_option(self):
        with patch.dict(os.environ, {"AIUSAGE_CLAUDE_API": "0"}):
            with patch("collector.urllib.request.urlopen") as urlopen:
                self.assertIsNone(collector.latest_claude_api())
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
