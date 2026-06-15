#!/usr/bin/env python3
"""Check whether the installed loop-creator plugin is behind its Git remote.

Read-only by default: this script never runs `git pull` or mutates the checkout.
It is meant for cron/ops prompts that ask the human to approve an update.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(args, cwd=PLUGIN_ROOT, text=True, capture_output=True, timeout=30)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _short(sha: str) -> str:
    return sha[:12] if sha else ""


def _read_version() -> str:
    text = (PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8")
    m = re.search(r'(?m)^version:\s*["\']?([^"\'\n]+)', text)
    return m.group(1).strip() if m else "unknown"


def check_update(remote: str = "origin", branch: str = "HEAD") -> dict[str, Any]:
    local_code, local_sha, local_err = _run(["git", "rev-parse", "HEAD"])
    if local_code != 0:
        return {"success": False, "error": f"cannot read local HEAD: {local_err or local_sha}"}

    remote_code, remote_out, remote_err = _run(["git", "ls-remote", remote, branch])
    if remote_code != 0:
        return {"success": False, "error": f"cannot read remote {remote}/{branch}: {remote_err or remote_out}"}
    remote_sha = remote_out.split()[0] if remote_out.split() else ""
    if not remote_sha:
        return {"success": False, "error": f"remote {remote}/{branch} returned no SHA"}

    url_code, remote_url, _ = _run(["git", "remote", "get-url", remote])
    if url_code != 0:
        remote_url = ""

    update_available = local_sha != remote_sha
    return {
        "success": True,
        "plugin": "loop-creator",
        "local_version": _read_version(),
        "remote": remote,
        "branch": branch,
        "remote_url": remote_url,
        "local_sha": local_sha,
        "remote_sha": remote_sha,
        "local_short": _short(local_sha),
        "remote_short": _short(remote_sha),
        "update_available": update_available,
        "apply_command": "hermes plugins update loop-creator",
        "approval_required": True,
        "note": "Read-only check. It does not pull or install anything; ask the user before applying updates.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check loop-creator plugin upstream update availability")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="HEAD")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()
    data = check_update(args.remote, args.branch)
    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if not data.get("success"):
            print(f"loop-creator update check failed: {data.get('error')}")
        elif data.get("update_available"):
            print(f"loop-creator update available: {data['local_short']} -> {data['remote_short']}")
            print(f"Apply after approval: {data['apply_command']}")
        else:
            print(f"loop-creator is current: {data['local_version']} @ {data['local_short']}")
    return 0 if data.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
