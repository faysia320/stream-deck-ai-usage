"""Sanitized local usage collector for Stream Deck. Python 3.10+, stdlib only."""
import argparse
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AIUsageStreamDeck"
CLAUDE = DATA / "claude.json"
CLAUDE_API_STATE = DATA / "claude_api.json"
CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CLAUDE_API_MIN_INTERVAL = 30
# Claude accounts registered by herdr-harness (one config dir per login). Without it only the
# default account (CLAUDE_CONFIG_DIR or ~/.claude) is read, as before.
ACCOUNTS = Path.home() / ".config" / "herdr-harness" / "claude-accounts.json"
ACCOUNT_CACHE = "usage-cache.json"
# With the account list, account "a" is always this folder: the process environment only says
# which account was current when Stream Deck started, not where account "a" lives.
DEFAULT_ACCOUNT_DIR = Path.home() / ".claude"


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return round(max(0, min(100, value)), 1)


def timestamp(value):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return int(value)
    if isinstance(value, str):
        try:
            from datetime import datetime
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        except ValueError:
            pass
    return None


def window(raw):
    if not isinstance(raw, dict):
        return None
    used = number(raw.get("used_percentage"))
    reset = timestamp(raw.get("resets_at"))
    if used is None or (reset is not None and reset <= time.time()):
        return None
    return {"used": used, "reset": reset}


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_json(path, data):
    DATA.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(temp, path)


def claude_stdin():
    # Never persist the full statusline payload: it contains transcript paths and session data.
    try:
        raw = json.load(sys.stdin)
        limits = raw.get("rate_limits") or {}
        write_json(CLAUDE, {"updated": int(time.time()),
                            "five_hour": window(limits.get("five_hour")),
                            "seven_day": window(limits.get("seven_day"))})
    except (ValueError, OSError, TypeError, AttributeError):
        pass


def default_config_dir():
    root = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(root) if root else Path.home() / ".claude"


def claude_credentials_path():
    return default_config_dir() / ".credentials.json"


def claude_accounts():
    # [{key, dir}] in registration order; the default account is always first.
    data = read_json(ACCOUNTS)
    if not (isinstance(data, dict) and isinstance(data.get("accounts"), dict)):
        return [{"key": "a", "dir": default_config_dir()}]
    first = data["accounts"].get("a") if isinstance(data["accounts"].get("a"), dict) else {}
    found = [{"key": "a", "dir": Path(first["dir"]) if isinstance(first.get("dir"), str) else DEFAULT_ACCOUNT_DIR}]
    for key, account in data["accounts"].items():
        if key != "a" and isinstance(account, dict) and isinstance(account.get("dir"), str):
            found.append({"key": key, "dir": Path(account["dir"])})
    return found


def active_config_dir():
    # The user-level variable decides which account new Claude sessions use. This process may
    # have started before a switch, so read the registry instead of its own environment.
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, "CLAUDE_CONFIG_DIR")
            return Path(value) if value else None
    except (ImportError, OSError):
        root = os.environ.get("CLAUDE_CONFIG_DIR")
        return Path(root) if root else None


def same_dir(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def claude_access_token(path=None):
    # Read only. Refreshing is left to Claude Code so its sign-in is never disturbed,
    # and the token is never stored, logged or passed to the plugin.
    payload = read_json(path or claude_credentials_path())
    oauth = payload.get("claudeAiOauth") if isinstance(payload, dict) else None
    if not isinstance(oauth, dict):
        return None
    token = oauth.get("accessToken")
    expires = oauth.get("expiresAt")
    if not isinstance(token, str) or not token:
        return None
    if isinstance(expires, (int, float)) and expires / 1000 - 60 <= time.time():
        return None
    return token


def parse_claude_usage(payload):
    if not isinstance(payload, dict):
        return None
    result = {"updated": int(time.time()), "five_hour": None, "seven_day": None}
    for name in ("five_hour", "seven_day"):
        raw = payload.get(name)
        if isinstance(raw, dict):
            result[name] = window({"used_percentage": raw.get("utilization"),
                                   "resets_at": raw.get("resets_at")})
    return result if result["five_hour"] or result["seven_day"] else None


def retry_after(value):
    try:
        return min(3600, max(CLAUDE_API_MIN_INTERVAL, int(value)))
    except (TypeError, ValueError):
        return 300


def latest_claude_api(credentials=None, state_path=None):
    # Undocumented endpoint behind Claude Code's /usage. Any failure falls back to statusline data.
    if os.environ.get("AIUSAGE_CLAUDE_API") == "0":
        return None
    now = time.time()
    state_path = state_path or CLAUDE_API_STATE
    state = read_json(state_path)
    if isinstance(state, dict) and isinstance(state.get("next"), (int, float)) and now < state["next"]:
        return None
    token = claude_access_token(credentials)
    if not token:
        return None
    wait, result = CLAUDE_API_MIN_INTERVAL, None
    request = urllib.request.Request(CLAUDE_USAGE_URL, headers={
        "Accept": "application/json", "Authorization": f"Bearer {token}",
        "anthropic-beta": "oauth-2025-04-20"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            result = parse_claude_usage(json.loads(response.read(100000)))
    except urllib.error.HTTPError as error:
        wait = retry_after(error.headers.get("Retry-After")) if error.code == 429 else 300
    except (OSError, ValueError):
        pass
    try:
        write_json(state_path, {"next": int(now + wait)})
    except OSError:
        pass
    return result


def parse_codex_limits(payload):
    if not isinstance(payload, dict):
        return None
    buckets = payload.get("rateLimitsByLimitId") or {}
    raw = buckets.get("codex") if isinstance(buckets, dict) else None
    if not isinstance(raw, dict):
        raw = payload.get("rateLimits") or {}
    if not isinstance(raw, dict) or raw.get("limitId") not in (None, "codex"):
        return None
    result = {"updated": int(time.time()), "five_hour": None, "seven_day": None}
    names = {300: "five_hour", 10080: "seven_day"}
    for item in (raw.get("primary"), raw.get("secondary")):
        if not isinstance(item, dict) or item.get("windowDurationMins") not in names:
            continue
        used = number(item.get("usedPercent"))
        reset = timestamp(item.get("resetsAt"))
        if used is not None:
            result[names[item["windowDurationMins"]]] = {"used": used, "reset": reset}
    return result if result["five_hour"] or result["seven_day"] else None


def codex_executable():
    # The desktop app installs the CLI under a versioned directory that changes
    # on updates. A configured path is only a hint, never a permanent pin.
    configured = os.environ.get("CODEX_CLI_PATH")
    if configured and Path(configured).is_file():
        return configured
    on_path = shutil.which("codex.exe")
    if on_path:
        return on_path
    bin_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    try:
        candidates = (p for p in bin_dir.glob("*/codex.exe") if p.is_file())
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    except (OSError, ValueError):
        return None


def latest_codex():
    # Official Codex app-server uses the CLI's existing ChatGPT sign-in.
    executable = codex_executable()
    if not executable:
        return None
    process = None
    try:
        process = subprocess.Popen(
            [executable, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        messages = queue.Queue()
        def read_lines():
            for line in process.stdout:
                messages.put(line)
            messages.put(None)

        threading.Thread(target=read_lines, daemon=True).start()

        def send(message):
            process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            process.stdin.flush()

        def receive(request_id, deadline):
            while time.monotonic() < deadline:
                try:
                    line = messages.get(timeout=max(0.01, deadline - time.monotonic()))
                    if not line:
                        return None
                    message = json.loads(line)
                    if isinstance(message, dict) and message.get("id") == request_id:
                        return message.get("result")
                except (queue.Empty, ValueError, TypeError):
                    return None
            return None

        deadline = time.monotonic() + 32
        send({"method": "initialize", "id": 1, "params": {"clientInfo": {
            "name": "ai_usage_streamdeck", "title": "AI Usage Stream Deck", "version": "1.2.0"}}})
        if receive(1, deadline) is None:
            return None
        send({"method": "initialized", "params": {}})
        send({"method": "account/rateLimits/read", "id": 2})
        return parse_codex_limits(receive(2, deadline))
    except (OSError, ValueError, TypeError):
        return None
    finally:
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass


def fresh(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get("updated"), (int, float))             or time.time() - entry["updated"] > 3600:
        return None
    return entry


def account_usage(account, default):
    # API first; each account backs off on its own. The account's own cache (written here or
    # by its Claude sessions' statusline) is the fallback, never another account's numbers.
    cache = account["dir"] / ACCOUNT_CACHE
    state = CLAUDE_API_STATE if default else DATA / f"claude_api_{account['key']}.json"
    usage = latest_claude_api(account["dir"] / ".credentials.json", state)
    if usage:
        for path in ([CLAUDE] if default else []) + [cache]:
            try:
                write_json(path, usage)
            except OSError:
                pass
        return usage
    return fresh(read_json(cache)) or (fresh(read_json(CLAUDE)) if default else None)


def collect():
    accounts, active = claude_accounts(), active_config_dir()
    rows = []
    for i, account in enumerate(accounts):
        usage = account_usage(account, i == 0) or {}
        is_active = same_dir(account["dir"], active) if active else i == 0
        rows.append({"key": account["key"], "label": account["key"].upper(), "active": is_active,
                     "five_hour": usage.get("five_hour"), "seven_day": usage.get("seven_day"),
                     "updated": usage.get("updated")})
    current = next((r for r in rows if r["active"]), rows[0])
    claude = {k: current[k] for k in ("updated", "five_hour", "seven_day")} if current["updated"] else None
    return {"codex": latest_codex(), "claude": claude, "claude_accounts": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["collect", "claude-stdin"])
    args = parser.parse_args()
    if args.mode == "claude-stdin":
        claude_stdin()
    else:
        print(json.dumps(collect(), ensure_ascii=False))
