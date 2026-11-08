"""
Ask Claude from inside the app: one message = one run of Claude Code in print mode,

    claude -p --output-format stream-json ... -- "<your message>"

started as a subprocess. Claude Code prints one JSON object per line; translate() keeps
the few we show (answer text, which tool is running, the final result) and the web
server forwards them to the page as Server-Sent Events.

Locked down: no built-in tools at all (--tools ""), only the wardrobe MCP server
(--strict-mcp-config), only its tools allowed, nobody to approve anything else
(dontAsk). Runs on your Claude Pro login: API keys are stripped from the environment,
and a run that would bill an API key is stopped at startup.

Trimmed port of dijkstra/ui/claude_runner.py.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from . import config

WRITE_TOOLS = {"create_outfit", "update_item"}       # these change what the page shows
STRIP_ENV = ("ANTHROPIC_", "CLAUDECODE", "CLAUDE_CODE_")
SYSTEM = ("You are the stylist inside Liam's wardrobe app. Use only the wardrobe tools. "
          "Answer in at most 5 short sentences; name items exactly as they are called. "
          "When you suggest an outfit, save it with create_outfit so it appears in the app. "
          "Plain text only: no Markdown, no lists.")


def build_command(message: str, session_id: Optional[str], root: Path,
                  claude_bin: str = "claude", model: str = "sonnet") -> list[str]:
    mcp = {"mcpServers": {"wardrobe": {
        "command": sys.executable,                    # this venv's Python, absolute
        "args": ["-m", "wardrobe.mcp_server"],
        "env": {"WARDROBE_DATA": str(root)},          # same data folder as the web app
    }}}
    cmd = [claude_bin, "-p",
           "--output-format", "stream-json", "--verbose", "--include-partial-messages",
           "--model", model,
           "--tools", "",
           "--mcp-config", json.dumps(mcp), "--strict-mcp-config",
           "--allowedTools", "mcp__wardrobe__*",
           "--permission-mode", "dontAsk",
           "--append-system-prompt", SYSTEM]
    if session_id:
        cmd += ["--resume", session_id]
    return cmd + ["--", message]                      # "--": the message can never be a flag


def child_env() -> dict[str, str]:
    """Our environment minus anything that would switch Claude Code off your Pro login."""
    return {k: v for k, v in os.environ.items() if not k.startswith(STRIP_ENV)}


class RunState:
    def __init__(self) -> None:
        self.text_started = False
        self.seen_tools: set[str] = set()
        self.changed = False


def translate(msg: dict, state: RunState) -> list[dict]:
    """One stream-json line -> zero or more events for the page."""
    kind, subtype = msg.get("type"), msg.get("subtype")

    if kind == "system" and subtype == "init":
        if msg.get("apiKeySource") not in (None, "none"):
            return [{"type": "error", "fatal": True, "text":
                     "Stopped: Claude Code would bill an API key instead of your Pro login."}]
        return [{"type": "init", "session_id": msg.get("session_id")}]

    if kind == "stream_event" and msg.get("parent_tool_use_id") is None:
        ev = msg.get("event") or {}
        if ev.get("type") == "content_block_start":
            if (ev.get("content_block") or {}).get("type") == "text" and state.text_started:
                return [{"type": "text", "text": "\n\n"}]
        elif ev.get("type") == "content_block_delta":
            d = ev.get("delta") or {}
            if d.get("type") == "text_delta" and d.get("text"):
                state.text_started = True
                return [{"type": "text", "text": d["text"]}]
        return []

    if kind == "assistant":
        out = []
        for block in (msg.get("message") or {}).get("content") or []:
            if block.get("type") != "tool_use" or block.get("id") in state.seen_tools:
                continue
            state.seen_tools.add(block.get("id"))
            name = block.get("name", "?").removeprefix("mcp__wardrobe__")
            state.changed |= name in WRITE_TOOLS
            out.append({"type": "status", "text": name})
        return out

    if kind == "result":
        return [{"type": "result", "session_id": msg.get("session_id"),
                 "is_error": bool(msg.get("is_error")), "turns": msg.get("num_turns")}]
    return []


async def run(message: str, session_id: Optional[str], root: Path, claude_bin: str = "claude",
              on_start: Optional[Callable[[asyncio.subprocess.Process], None]] = None
              ) -> AsyncIterator[dict]:
    exe = shutil.which(claude_bin)
    if not exe:
        yield {"type": "error", "text": f"Can't find '{claude_bin}'. Is Claude Code installed and on PATH?"}
        return
    proc = await asyncio.create_subprocess_exec(
        *build_command(message, session_id, root, exe), cwd=config.REPO_ROOT, env=child_env(),
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, limit=8 * 1024 * 1024)
    if on_start:
        on_start(proc)
    state, got_result = RunState(), False
    try:
        async for raw in proc.stdout:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for event in translate(msg, state):
                got_result |= event["type"] == "result"
                yield event
                if event.get("fatal"):
                    proc.terminate()
                    return
        code = await proc.wait()
        if state.changed:
            yield {"type": "changed"}
        if code != 0 and not got_result:
            err = (await proc.stderr.read()).decode(errors="replace").strip()[-300:]
            yield {"type": "error", "text": f"claude exited with code {code}. {err}".strip()}
    finally:
        if proc.returncode is None:
            proc.terminate()
