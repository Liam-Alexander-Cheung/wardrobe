"""
The Ask-Claude runner and endpoint. A fake `claude` executable replays recorded
stream-json lines, so no test talks to the real Claude or uses quota.
"""

import json
import os
import stat
import sys
import textwrap

import pytest
from fastapi.testclient import TestClient

from conftest import BASE, fake_remover
from wardrobe import ask
from wardrobe.app import create_app

INIT = {"type": "system", "subtype": "init", "session_id": "s1", "model": "claude-sonnet-5-5",
        "apiKeySource": "none", "mcp_servers": [{"name": "wardrobe", "status": "connected"}]}


def delta(text):
    return {"type": "stream_event", "event": {"type": "content_block_delta",
                                              "delta": {"type": "text_delta", "text": text}}}


def tool(tid, name):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid,
                                                          "name": f"mcp__wardrobe__{name}", "input": {}}]}}


RESULT = {"type": "result", "subtype": "success", "result": "Let me look\n\nSaved.",
          "session_id": "s1", "is_error": False, "num_turns": 3, "total_cost_usd": 0.05}
HAPPY = [INIT, delta("Let me look"), tool("t1", "list_items"), tool("t1", "list_items"),
         tool("t2", "create_outfit"),
         {"type": "stream_event", "event": {"type": "content_block_start", "content_block": {"type": "text"}}},
         delta("Saved."), RESULT]


@pytest.fixture
def fake_claude(tmp_path):
    """Write an executable that records its argv/env and prints the given lines."""
    def make(lines, exit_code=0):
        (tmp_path / "lines.jsonl").write_text("\n".join(json.dumps(l) for l in lines))
        script = tmp_path / "claude"
        script.write_text(textwrap.dedent(f"""\
            #!{sys.executable}
            import json, os, sys
            json.dump({{"argv": sys.argv[1:], "env": dict(os.environ)}},
                      open({str(tmp_path / 'call.json')!r}, "w"))
            print(open({str(tmp_path / 'lines.jsonl')!r}).read(), flush=True)
            sys.exit({exit_code})
        """))
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return str(script)
    return make


def last_call(tmp_path):
    return json.loads((tmp_path / "call.json").read_text())


def events(response):
    return [json.loads(l[6:]) for l in response.text.splitlines() if l.startswith("data: ")]


def client_for(data_dir, claude_bin):
    app = create_app(data_dir=data_dir, remover=fake_remover, claude_bin=claude_bin)
    return TestClient(app, base_url=BASE, headers={"origin": BASE})


# --- the command line -----------------------------------------------------------------

def test_command_is_locked_down(tmp_path):
    cmd = ask.build_command("hi", None, tmp_path / "data", claude_bin="/bin/claude")
    assert cmd[:2] == ["/bin/claude", "-p"]
    assert cmd[cmd.index("--tools") + 1] == ""                     # no Bash/Read/Write/Web…
    assert cmd[cmd.index("--allowedTools") + 1] == "mcp__wardrobe__*"
    assert "--strict-mcp-config" in cmd                             # only our MCP server
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    mcp = json.loads(cmd[cmd.index("--mcp-config") + 1])["mcpServers"]["wardrobe"]
    assert mcp["command"] == sys.executable
    assert mcp["env"]["WARDROBE_DATA"] == str(tmp_path / "data")    # same data as the app
    assert cmd[-2:] == ["--", "hi"]                                 # message can't be a flag
    assert "--resume" not in cmd


def test_command_resumes_a_session(tmp_path):
    cmd = ask.build_command("and shoes?", "3f2a9c1e-0000-4000-8000-000000000000", tmp_path)
    assert cmd[cmd.index("--resume") + 1] == "3f2a9c1e-0000-4000-8000-000000000000"


def test_child_env_drops_api_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = ask.child_env()
    assert "ANTHROPIC_API_KEY" not in env and "CLAUDECODE" not in env and "PATH" in env


# --- the stream parser ------------------------------------------------------------------

def test_translate_happy_path():
    state = ask.RunState()
    out = [e for line in HAPPY for e in ask.translate(line, state)]
    assert [e["type"] for e in out] == ["init", "text", "status", "status", "text", "text", "result"]
    assert [e["text"] for e in out if e["type"] == "status"] == ["list_items", "create_outfit"]
    assert "".join(e["text"] for e in out if e["type"] == "text") == "Let me look\n\nSaved."
    assert out[-1]["session_id"] == "s1" and state.changed


def test_translate_refuses_api_key_billing():
    out = ask.translate({**INIT, "apiKeySource": "ANTHROPIC_API_KEY"}, ask.RunState())
    assert out[0]["type"] == "error" and out[0]["fatal"]


def test_read_only_run_is_not_a_change():
    state = ask.RunState()
    for line in [INIT, tool("t1", "list_items"), RESULT]:
        ask.translate(line, state)
    assert not state.changed


# --- the endpoint ------------------------------------------------------------------------

def test_ask_streams_events_and_flags_changes(data_dir, fake_claude, tmp_path):
    with client_for(data_dir, fake_claude(HAPPY)) as c:
        r = c.post("/api/ask", json={"message": "outfit for school, cold day"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    evs = events(r)
    assert [e["type"] for e in evs][-2:] == ["result", "changed"]
    call = last_call(tmp_path)
    assert call["argv"][-1] == "outfit for school, cold day"
    assert "ANTHROPIC_API_KEY" not in call["env"]


def test_ask_reports_a_crash(data_dir, fake_claude):
    with client_for(data_dir, fake_claude([INIT], exit_code=1)) as c:
        evs = events(c.post("/api/ask", json={"message": "hi"}))
    assert evs[-1]["type"] == "error"


def test_ask_validates_input(data_dir, fake_claude):
    with client_for(data_dir, fake_claude(HAPPY)) as c:
        assert c.post("/api/ask", json={"message": ""}).status_code == 422
        assert c.post("/api/ask", json={"message": "x" * 3000}).status_code == 422
        assert c.post("/api/ask", json={"message": "hi", "session_id": "--dangerous"}).status_code == 422


def test_ask_needs_our_origin(data_dir, fake_claude):
    app = create_app(data_dir=data_dir, remover=fake_remover, claude_bin=fake_claude(HAPPY))
    r = TestClient(app, base_url=BASE).post("/api/ask", json={"message": "hi"},
                                            headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_missing_claude_is_a_clear_error(data_dir):
    with client_for(data_dir, "/nonexistent/claude") as c:
        evs = events(c.post("/api/ask", json={"message": "hi"}))
    assert evs[-1]["type"] == "error" and "claude" in evs[-1]["text"].lower()
