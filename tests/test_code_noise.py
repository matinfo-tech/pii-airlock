"""Code-like input: model detections that do not read as a name are dropped (hook filter)."""

from __future__ import annotations

import io
import json

import pytest

from pii_scrub.config import Config
from pii_scrub.engine import Detection
from pii_scrub.hooks import _common as common


def _span(text: str, value: str) -> tuple[int, int]:
    start = text.index(value)
    return start, start + len(value)


@pytest.mark.parametrize("text,value", [
    ("npm test", "npm"),
    ("cat customer.txt", "customer.txt"),
    ("git log --oneline -5", "git log --oneline -5"),
    ("cd docs && npm run build", "&& npm"),
    ("go test ./...", "./"),
    ("git diff HEAD~1 -- src/Header.vue", "Header.vue"),
    ("git rebase -i HEAD~3", "HEAD"),
    ("curl -s https://api.github.com/repos/foo/bar", "-s https://api.github.com/repos/foo/bar"),
    ("Build the Docker image", "Docker"),
    ("Push branch to GitHub", "Push"),
    ("Restart the Nginx service", "Restart the"),
    ("Commit the changes", "Commit the changes"),
    ('git commit -m "Fix login redirect"', "Fix"),
    ('gh pr create --title "Add dark mode"', '"Add'),
    ("class .*Engine", ".*Engine"),
    ("function handleSubmit", "handleSubmit"),
    ("class UserService:", "UserService"),
    ("raise ValueError", "ValueError"),
    ("return None", "None"),
    ("    # Fails below the threshold", "Fails"),
    ("// Retry once. Then give up", "Then"),
    ("src/App.tsx", "App.tsx"),
])
def test_command_line_noise_does_not_read_as_a_name(text, value):
    assert not common._reads_as_a_name(text, *_span(text, value))


@pytest.mark.parametrize("text,value", [
    ('git commit -m "Thanks to Sarah Johnson for the review"', "Sarah Johnson"),
    ('git commit -m "Sarah Johnson fixed the build"', "Sarah Johnson"),
    ("sqlite3 crm.db \"SELECT * FROM c WHERE name = 'David Miller'\"", "David Miller'"),
    ('grep -rn "Dupont" contracts/', "Dupont"),
    ("grep -rn Dupont contracts/", "Dupont"),
    ('echo "Refund for Jean-Pierre Dubois"', "Jean-Pierre Dubois"),
    ('echo "meeting with Jean DUPONT"', "Jean DUPONT"),
    ('echo "ship to Charles de Gaulle"', "Charles de Gaulle"),
    ('echo "office in London"', "London"),
    ("Dupont", "Dupont"),
    ("# Reported by Michael Brown, see ticket", "Michael Brown"),
    ("    # Ask Dupont about this", "Dupont"),
    ('USERS = [{"name": "Sarah Johnson"}]', "Sarah Johnson"),
    ('client = "McDonald"', "McDonald"),
    ("const owner = 'Jean-Pierre Dubois'", "Jean-Pierre Dubois"),
])
def test_names_in_a_command_line_are_kept(text, value):
    assert common._reads_as_a_name(text, *_span(text, value))


@pytest.mark.parametrize("tool,tool_input,texts,expected", [
    ("Grep", {"pattern": "Dupont", "path": "src"}, ["Dupont", "src"], [True, True]),
    ("glob", {"pattern": "*.py"}, ["*.py"], [True]),
    ("Read", {"file_path": "notes.md"}, ["notes.md", "Jean Dupont"], [True, False]),
    ("Read", {"file_path": "app.py"}, ["app.py", "Jean Dupont"], [True, True]),
    ("Edit", {"file_path": "src/App.tsx", "old_string": "a", "new_string": "b"},
     ["b", "a"], [True, True]),
    ("Edit", {"file_path": "README.md", "old_string": "a", "new_string": "b"},
     ["b", "a"], [False, False]),
    ("Write", {"file_path": "fixtures/users.json", "content": "x"},
     ["x", "fixtures/users.json"], [False, True]),
    ("create", {"path": "Dockerfile", "file_text": "FROM x"}, ["Dockerfile", "FROM x"],
     [True, True]),
    ("NotebookEdit", {"new_source": "df.head()"}, ["df.head()"], [True]),
    ("WebSearch", {"query": "jean dupont"}, ["jean dupont"], [False]),
    ("mcp__crm__find", {"name": "Dupont"}, ["Dupont"], [False]),
])
def test_which_texts_count_as_code(tool, tool_input, texts, expected):
    assert common._code_texts(tool, tool_input, texts) == expected


def test_pattern_detections_are_never_dropped():
    text = "npm run mail jean@acme.fr"
    dets = [Detection("ORGANIZATION", 0, 3, 0.85), Detection("EMAIL_ADDRESS", 13, 25, 1.0),
            Detection("IBAN_CODE", 0, 3, 1.0)]
    ((_, kept),) = common._drop_code_noise([(text, dets)])
    assert [d.entity_type for d in kept] == ["EMAIL_ADDRESS", "IBAN_CODE"]


def test_deny_terms_labelled_as_a_name_are_never_dropped():
    text = "grep -r dupont ."
    deny = Detection("PERSON", 8, 14, 1.0)  # `pii-airlock deny dupont --as PERSON`
    assert common._drop_code_noise([(text, [deny])]) == [(text, [deny])]


class _NoisyEngine:
    """Reads the first word of every text as an organisation, as small models do."""

    def __init__(self, *_a, **_k):
        pass

    def prime(self, texts, language=None):
        pass

    def detect(self, text, language=None):
        return [Detection("ORGANIZATION", 0, len(text.split()[0]), 0.85)]


def _reply(monkeypatch, capsys, event):
    monkeypatch.setattr(common.daemon, "detect", lambda cwd, texts: None)
    monkeypatch.setattr(common.daemon, "spawn", lambda cwd=None: None)
    monkeypatch.setattr(common, "ScrubEngine", _NoisyEngine)
    monkeypatch.setattr(common, "load_config", lambda **_k: Config())
    monkeypatch.setattr(common.sys, "stdin", io.StringIO(json.dumps(event)))
    common.run_pre_tool_use()
    out = capsys.readouterr().out
    return json.loads(out) if out.strip() else None


@pytest.mark.parametrize("event", [
    {"tool_name": "Bash", "tool_input": {"command": "npm test"}},
    {"toolName": "bash", "toolArgs": {"command": "npm test", "description": "Run tests"}},
    {"toolName": "powershell", "toolArgs": {"command": "npm test"}},
    {"tool_name": "Grep", "tool_input": {"pattern": "useState", "path": "src"}},
    {"tool_name": "Edit", "tool_input": {"file_path": "a.py", "old_string": "pass",
                                         "new_string": "return None"}},
], ids=["claude-bash", "copilot-bash", "copilot-powershell", "grep", "edit-source"])
def test_plain_code_input_is_allowed_silently(monkeypatch, capsys, event):
    assert _reply(monkeypatch, capsys, event) is None


def test_prose_keeps_every_model_detection(monkeypatch, capsys):
    event = {"tool_name": "Write", "tool_input": {"file_path": "notes.md",
                                                  "content": "npm is mentioned in prose"}}
    reply = _reply(monkeypatch, capsys, event)
    assert "ORGANIZATION" in reply["permissionDecisionReason"]
