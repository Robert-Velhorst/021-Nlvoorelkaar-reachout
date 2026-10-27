"""Owned hosted causal regression evidence; no provider access or original case edits."""

from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

assert os.environ.get("GITHUB_ACTIONS") == "true"
assert os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
assert os.environ.get("GITHUB_REPOSITORY") == "Robert-Velhorst/021-Nlvoorelkaar-reachout"

root = Path.cwd()
out = Path(os.environ["RUNNER_TEMP"]) / "hai-origin-boundary-evidence"
out.mkdir()
base = "0b71dccc4b78d148360fb8c1aad978c91bea38a4"
baseline = Path(os.environ["RUNNER_TEMP"]) / "hai-origin-baseline"
new_case = "tests/test_hai_bridge_origin_boundary.py"


def git(folder, *args):
    return subprocess.check_output(["git", "-C", str(folder), *args])


def snapshot(folder, revision):
    result = {}
    for entry in git(folder, "ls-tree", "-r", "-z", revision).split(b"\0"):
        if not entry:
            continue
        meta, name = entry.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        assert kind == "blob" and mode in {"100644", "100755"}
        data = git(folder, "cat-file", "blob", oid)
        result[name.decode()] = {"blob": oid, "sha256": hashlib.sha256(data).hexdigest()}
    return result


def assert_payloads(folder, rows):
    for name, row in rows.items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == row["sha256"], name


head = git(root, "rev-parse", "HEAD").decode().strip()
before = snapshot(root, head)
original = snapshot(root, base)
assert_payloads(root, before)
original_unchanged = {
    name: row for name, row in original.items()
    if name not in {"connectors/hai_bridge.py", "docs/HAI_CONNECTOR.md"}
}
assert all(before[name] == row for name, row in original_unchanged.items())
assert new_case not in original
(out / "source-before.json").write_text(json.dumps({"head": head, "payloads": before}, indent=2) + "\n")
(out / "base-source.json").write_text(json.dumps({"head": base, "payloads": original}, indent=2) + "\n")

commands = []
summary = {
    "head": head, "base": base,
    "original_cases_helpers_fixtures_assertions_selectors_timeouts_unchanged": True,
    "all_other_base_payloads_unchanged": len(original_unchanged),
    "full_original_suite_or_complete_repository_qualified": False,
    "CodeQL_alert_dismissed_or_closed": False,
    "provider_requests_manual_deployment_or_live_data_changes": False,
}
try:
    subprocess.run(["git", "worktree", "add", "--detach", str(baseline), base], check=True)
    shutil.copyfile(root / new_case, baseline / new_case)
    for label, folder in [("baseline", baseline), ("candidate", root)]:
        command = [sys.executable, "-m", "pytest", "-q", new_case, "-ra"]
        with (out / (label + "-new-regressions.log")).open("wb") as stream:
            completed = subprocess.run(command, cwd=folder, stdout=stream, stderr=subprocess.STDOUT, check=False)
        commands.append({"label": label, "command": ["python", "-m", "pytest", "-q", new_case, "-ra"], "returncode": completed.returncode})
        summary[label + "_exit"] = completed.returncode
    assert hashlib.sha256((baseline / new_case).read_bytes()).hexdigest() == before[new_case]["sha256"]
    assert_payloads(baseline, original)
finally:
    assert_payloads(root, before)
    (out / "source-after.json").write_text(json.dumps({"head": head, "payloads": before}, indent=2) + "\n")
    (out / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

assert summary.get("baseline_exit") == 1, "Expected actual case failures, not collection/setup failure"
assert summary.get("candidate_exit") == 0
print(json.dumps(summary))
