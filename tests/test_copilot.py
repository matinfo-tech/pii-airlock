"""GitHub Copilot hook support: payload normalization, reply format, installer."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest

import pii_scrub.hookinstall as hookinstall
from pii_scrub.hooks import _common


def _run(monkeypatch, capsys, event, found=("EMAIL_ADDRESS",)):
    seen: list[str] = []

    def analyze(_config, _event, texts):
        seen.extend(texts)
        return [SimpleNamespace(entity_type=t) for t in found]

    monkeypatch.setattr(_common, "_analyze", analyze)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
    _common.run_pre_tool_use()
    out = capsys.readouterr().out
    return (json.loads(out) if out.strip() else None), seen


def test_copilot_payload_is_scanned_and_answered_in_copilot_format(monkeypatch, capsys):
    event = {"sessionId": "s", "cwd": "/tmp", "toolName": "bash",
             "toolArgs": json.dumps({"command": "mail jean@acme.fr"})}
    reply, seen = _run(monkeypatch, capsys, event)
    assert seen == ["mail jean@acme.fr"]
    assert reply["permissionDecision"] in ("ask", "deny")
    assert "pii-airlock" in reply["permissionDecisionReason"]


def test_copilot_tools_with_unknown_names_are_still_scanned(monkeypatch, capsys):
    event = {"toolName": "some_new_tool", "toolArgs": json.dumps({"a": {"b": ["x@y.io"]}})}
    _, seen = _run(monkeypatch, capsys, event)
    assert seen == ["x@y.io"]


def test_copilot_unparseable_args_are_scanned_as_text(monkeypatch, capsys):
    event = {"toolName": "bash", "toolArgs": "not json jean@acme.fr"}
    reply, seen = _run(monkeypatch, capsys, event)
    assert seen == ["not json jean@acme.fr"] and reply is not None


def test_copilot_clean_call_is_allowed_silently(monkeypatch, capsys):
    reply, _ = _run(monkeypatch, capsys, {"toolName": "bash", "toolArgs": "{}"}, found=())
    assert reply is None


def test_copilot_view_scans_the_file_content(monkeypatch, capsys, tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("contact jean@acme.fr")
    event = {"toolName": "view", "cwd": str(tmp_path),
             "toolArgs": json.dumps({"path": "notes.txt"})}
    _, seen = _run(monkeypatch, capsys, event)
    assert "contact jean@acme.fr" in seen


# Payloads recorded from a live Copilot CLI 1.0.114 session (2026-11-21), paths shortened.
# `toolArgs` arrives as an object, with `timestamp` and `toolCallId` alongside.
_LIVE = {"sessionId": "28c93ba9-c31c-4287-bcba-05c888c9bfa6", "timestamp": 1795217573094,
         "cwd": "/tmp/repo", "toolCallId": "toolu_01WanfVkmucQqEqmHrE9PSJ6"}
_LIVE_CALLS = [
    ("bash", {"command": "echo 'mail jean.dupont@acme-corp.ch'", "description": "Echo mail"},
     ["echo 'mail jean.dupont@acme-corp.ch'", "Echo mail"]),
    ("create", {"path": "/tmp/repo/lead.txt", "file_text": "Marie Curchod, +41 79 555 98 76\n"},
     ["/tmp/repo/lead.txt", "Marie Curchod, +41 79 555 98 76\n"]),
    ("edit", {"path": "/tmp/repo/notes.txt", "old_str": "hello world",
              "new_str": "call Marie Curchod"},
     ["/tmp/repo/notes.txt", "hello world", "call Marie Curchod"]),
    ("grep", {"pattern": "marie.curchod@acme-corp.ch", "paths": "/tmp/repo"},
     ["marie.curchod@acme-corp.ch", "/tmp/repo"]),
    ("glob", {"pattern": "*.txt", "paths": "/tmp/repo"}, ["*.txt", "/tmp/repo"]),
]


@pytest.mark.parametrize("tool,args,expected", _LIVE_CALLS, ids=[c[0] for c in _LIVE_CALLS])
def test_live_copilot_payloads_are_scanned(monkeypatch, capsys, tool, args, expected):
    reply, seen = _run(monkeypatch, capsys, {**_LIVE, "toolName": tool, "toolArgs": args})
    assert sorted(seen) == sorted(expected)
    assert reply["permissionDecision"] in ("ask", "deny")


def test_live_copilot_view_payload_scans_the_file_content(monkeypatch, capsys, tmp_path):
    f = tmp_path / "customer.txt"
    f.write_text("Email: jean.dupont@acme-corp.ch")
    event = {**_LIVE, "cwd": str(tmp_path), "toolName": "view", "toolArgs": {"path": str(f)}}
    _, seen = _run(monkeypatch, capsys, event)
    assert "Email: jean.dupont@acme-corp.ch" in seen


def test_live_copilot_clean_call_is_allowed_silently(monkeypatch, capsys):
    event = {**_LIVE, "toolName": "bash",
             "toolArgs": {"command": "echo hello", "description": "Echo hello"}}
    reply, _ = _run(monkeypatch, capsys, event, found=())
    assert reply is None


def test_one_reply_serves_claude_code_and_copilot(monkeypatch, capsys):
    event = {"tool_name": "Bash", "tool_input": {"command": "mail jean@acme.fr"}}
    reply, _ = _run(monkeypatch, capsys, event)
    nested = reply["hookSpecificOutput"]
    assert nested["hookEventName"] == "PreToolUse"
    assert nested["permissionDecision"] == reply["permissionDecision"]
    assert nested["permissionDecisionReason"] == reply["permissionDecisionReason"]


def test_copilot_snake_case_alias_with_json_string_input(monkeypatch, capsys):
    # PascalCase events (and .claude/settings.json hooks read by Copilot CLI) arrive
    # as tool_name / tool_input, the input possibly still a JSON string.
    event = {"hook_event_name": "PreToolUse", "tool_name": "bash",
             "tool_input": json.dumps({"command": "mail jean@acme.fr"})}
    reply, seen = _run(monkeypatch, capsys, event)
    assert seen == ["mail jean@acme.fr"] and reply["permissionDecision"] in ("ask", "deny")


@pytest.mark.parametrize("tool", ["ask_user", "bash", "create", "edit", "glob", "grep",
                                  "powershell", "task", "view", "web_fetch", "web_search",
                                  "str_replace_editor", "apply_patch", "rg", "update_todo"])
def test_every_documented_copilot_tool_is_scanned(monkeypatch, capsys, tool):
    event = {"toolName": tool, "toolArgs": json.dumps({"anything": "jean@acme.fr"})}
    reply, seen = _run(monkeypatch, capsys, event)
    assert seen == ["jean@acme.fr"] and reply is not None


def test_known_tool_with_unfamiliar_arguments_is_still_scanned(monkeypatch, capsys):
    # A harness may name a tool like Claude Code's but use other argument names.
    event = {"tool_name": "Write", "tool_input": {"text": "jean@acme.fr"}}
    _, seen = _run(monkeypatch, capsys, event)
    assert seen == ["jean@acme.fr"]


def test_claude_edit_still_ignores_the_file_path(monkeypatch, capsys):
    event = {"tool_name": "Edit", "tool_input": {
        "file_path": "/home/jean.dupont/a.txt", "old_string": "a", "new_string": "b"}}
    _, seen = _run(monkeypatch, capsys, event, found=())
    assert sorted(seen) == ["a", "b"]


def test_install_copilot_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path, changed = hookinstall.install_copilot("project")
    assert changed and path == tmp_path / ".github" / "hooks" / "pii-airlock.json"
    data = json.loads(path.read_text())
    assert data["version"] == 1
    assert data["hooks"]["preToolUse"][0]["bash"] == "pii-airlock hook pre-tool-use"
    assert hookinstall.install_copilot("project") == (path, False)


def test_install_copilot_user_scope_honours_copilot_home(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "cp"))
    path, _ = hookinstall.install_copilot("user")
    assert path == tmp_path / "cp" / "hooks" / "pii-airlock.json" and path.is_file()


@pytest.mark.parametrize("scope", ["project", "user"])
def test_cli_target_copilot(tmp_path, monkeypatch, scope):
    from typer.testing import CliRunner

    import pii_scrub.cli as cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "cp"))
    result = CliRunner().invoke(cli.app, ["install-hook", "--target", "copilot", "--scope", scope])
    assert result.exit_code == 0 and "preToolUse" in result.output
