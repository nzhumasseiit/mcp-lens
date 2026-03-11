#!/usr/bin/env python3
"""
mcp-trace: stdio proxy for MCP servers.
wraps any MCP server, logs every tool call live.

usage: python interceptor.py npx -y @modelcontextprotocol/server-filesystem /tmp
"""

import sys
import json
import time
import asyncio
from datetime import datetime
from collections import Counter

# ── Terminal colors (zero dependencies) ──────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GREEN= "\033[42m"

# ── State ────────────────-────────────────────────────────────────────────────
call_log: list[dict] = []
pending: dict[str, dict] = {}   # request_id → {method, started_at, params}
total_calls = 0
total_errors = 0
session_start = time.time()


def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def render_header():
    uptime = time.time() - session_start
    sys.stderr.write(
        f"\n{C.BOLD}{C.CYAN}┌─ mcp-trace ──────────────────────────────────────────────────┐{C.RESET}\n"
        f"{C.CYAN}│{C.RESET} {C.BOLD}Live MCP stdio interceptor{C.RESET}   "
        f"uptime: {C.YELLOW}{uptime:.1f}s{C.RESET}   "
        f"calls: {C.GREEN}{total_calls}{C.RESET}   "
        f"errors: {C.RED}{total_errors}{C.RESET}\n"
        f"{C.CYAN}└──────────────────────────────────────────────────────────────┘{C.RESET}\n"
    )


def render_call(entry: dict):
    """render one tool call line."""
    status = entry.get("status", "pending")
    latency = entry.get("latency_ms")
    method = entry.get("method", "unknown")
    req_id = entry.get("id", "?")
    ts = entry.get("timestamp", now_str())

    # Status indicator
    if status == "success":
        indicator = f"{C.BG_GREEN}{C.BOLD} ✓ {C.RESET}"
        latency_str = f"{C.GREEN}{latency:.0f}ms{C.RESET}" if latency else ""
    elif status == "error":
        indicator = f"{C.BG_RED}{C.BOLD} ✗ {C.RESET}"
        latency_str = f"{C.RED}{latency:.0f}ms{C.RESET}" if latency else ""
    else:
        indicator = f"{C.YELLOW} ◌ {C.RESET}"
        latency_str = f"{C.DIM}pending{C.RESET}"

    # Method coloring
    if "tool" in method.lower() or "call" in method.lower():
        method_str = f"{C.MAGENTA}{C.BOLD}{method}{C.RESET}"
    elif "initialize" in method.lower():
        method_str = f"{C.BLUE}{method}{C.RESET}"
    else:
        method_str = f"{C.CYAN}{method}{C.RESET}"

    # Params preview
    params = entry.get("params", {})
    params_preview = ""
    if params:
        if "name" in params:           # tool call has a name
            params_preview = f" → {C.BOLD}{params['name']}{C.RESET}"
            if "arguments" in params:
                args_str = json.dumps(params["arguments"], ensure_ascii=False)
                if len(args_str) > 60:
                    args_str = args_str[:57] + "..."
                params_preview += f" {C.DIM}{args_str}{C.RESET}"
        else:
            flat = json.dumps(params, ensure_ascii=False)
            if len(flat) > 80:
                flat = flat[:77] + "..."
            params_preview = f" {C.DIM}{flat}{C.RESET}"

    # Error detail
    error_line = ""
    if status == "error" and entry.get("error"):
        err = entry["error"]
        msg = err.get("message", str(err))[:100]
        error_line = f"\n     {C.RED}↳ {msg}{C.RESET}"

    sys.stderr.write(
        f"{C.DIM}{ts}{C.RESET} {indicator} "
        f"{C.DIM}#{req_id:>4}{C.RESET} "
        f"{method_str}{params_preview} "
        f"{latency_str}"
        f"{error_line}\n"
    )
    sys.stderr.flush()

def render_summary():
    """Print session summary on exit with tool frequency."""
    duration = time.time() - session_start
    sys.stderr.write(
        f"\n{C.BOLD}{C.CYAN}── Session Summary ────────────────────────────────────────────{C.RESET}\n"
    )
    
    if not call_log:
        sys.stderr.write(f"  {C.DIM}No messages recorded.{C.RESET}\n")
    else:
        tool_calls = [e for e in call_log if "tools/call" in e.get("method", "")]
        latencies = [e["latency_ms"] for e in call_log if e.get("latency_ms")]
        errors = [e for e in call_log if e.get("status") == "error"]
        
        method_names = []
        for e in call_log:
            m = e.get("method", "unknown")
            if "tools/call" in m:
                name = e.get("params", {}).get("name")
                method_names.append(f"tool:{name}" if name else m)
            else:
                method_names.append(m)
        
        top_methods = Counter(method_names).most_common(3)

        sys.stderr.write(f"  Total messages : {C.BOLD}{len(call_log)}{C.RESET}\n")
        sys.stderr.write(f"  Tool calls     : {C.MAGENTA}{len(tool_calls)}{C.RESET}\n")
        sys.stderr.write(f"  Errors         : {C.RED}{len(errors)}{C.RESET}\n")
        
        if top_methods:
            method_str = ", ".join([f"{name} ({count})" for name, count in top_methods])
            sys.stderr.write(f"  Top Methods    : {C.BLUE}{method_str}{C.RESET}\n")

        if latencies:
            avg = sum(latencies) / len(latencies)
            sys.stderr.write(f"  Avg latency    : {C.YELLOW}{avg:.0f}ms{C.RESET}\n")

        if errors:
            sys.stderr.write(f"\n  {C.RED}{C.BOLD}Failed calls:{C.RESET}\n")
            for e in errors[:5]:
                name = e.get("params", {}).get("name", e.get("method", "unknown"))
                err_msg = e.get("error", {}).get("message", "unknown error")
                sys.stderr.write(f"    {C.RED}✗{C.RESET} {name} → {err_msg}\n")

    sys.stderr.write(
        f"  Duration       : {C.DIM}{duration:.1f}s{C.RESET}\n"
        f"{C.CYAN}───────────────────────────────────────────────────────────────{C.RESET}\n\n"
    )


def process_message(raw: bytes, direction: str) -> bytes:
    global total_calls, total_errors

    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    msg_id = msg.get("id")
    method = msg.get("method")

    if direction == "client→server" and method:
        total_calls += 1
        entry = {
            "id": msg_id,
            "method": method,
            "params": msg.get("params", {}),
            "timestamp": now_str(),
            "started_at": time.time(),
            "status": "pending",
            "direction": direction,
        }
        call_log.append(entry)
        if msg_id is not None:
            pending[str(msg_id)] = entry
        render_call(entry)

    elif direction == "server→client" and msg_id is not None:
        key = str(msg_id)
        if key in pending:
            entry = pending.pop(key)
            entry["latency_ms"] = (time.time() - entry["started_at"]) * 1000
            if "error" in msg:
                entry["status"] = "error"
                entry["error"] = msg["error"]
                total_errors += 1
            else:
                entry["status"] = "success"
                entry["result_preview"] = str(msg.get("result", ""))[:100]
            render_call(entry)

    return raw
    
# ── Async proxy ───────────────────────────────────────────────────────────────

async def pipe_stream(reader: asyncio.StreamReader,
                      writer,
                      direction: str,
                      is_subprocess_stdin: bool = False):
    """Read newline-delimited JSON from reader, intercept, write to writer."""
    buffer = b""
    while True:
        try:
            chunk = await reader.read(4096)
            if not chunk:
                break
            buffer += chunk

            # MCP stdio uses newline-delimited JSON
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue

                intercepted = process_message(line, direction)

                if is_subprocess_stdin:
                    writer.write(intercepted + b"\n")
                    await writer.drain()
                else:
                    # writing to sys.stdout
                    sys.stdout.buffer.write(intercepted + b"\n")
                    sys.stdout.buffer.flush()

        except (asyncio.IncompleteReadError, ConnectionResetError):
            break
        except Exception as e:
            sys.stderr.write(f"{C.RED}[mcp-trace] pipe error: {e}{C.RESET}\n")
            break


async def run_proxy(cmd: list[str]):
    """Launch the MCP server as a subprocess and proxy its stdio."""
    render_header()
    sys.stderr.write(
        f"{C.DIM}Intercepting: {' '.join(cmd)}{C.RESET}\n"
        f"{C.DIM}{'─'*65}{C.RESET}\n\n"
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Pipe stderr from subprocess directly to our stderr (server logs)
    async def forward_stderr():
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            sys.stderr.write(f"{C.DIM}[server] {line.decode(errors='replace').rstrip()}{C.RESET}\n")
            sys.stderr.flush()

    async def read_stdin():
        """Read from our own stdin (from Claude) and forward to subprocess."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)

        buffer = b""
        while True:
            try:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    intercepted = process_message(line, "client→server")
                    proc.stdin.write(intercepted + b"\n")
                    await proc.stdin.drain()
            except Exception:
                break
        proc.stdin.close()

    async def read_stdout():
        """Read from subprocess stdout and forward to our stdout (to Claude)."""
        buffer = b""
        while True:
            try:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    intercepted = process_message(line, "server→client")
                    sys.stdout.buffer.write(intercepted + b"\n")
                    sys.stdout.buffer.flush()
            except Exception:
                break

    try:
        await asyncio.gather(
            read_stdin(),
            read_stdout(),
            forward_stderr(),
        )
    finally:
        render_summary()
        try:
            proc.terminate()
        except Exception:
            pass


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write(
            f"{C.BOLD}mcp-trace{C.RESET} — Live MCP stdio interceptor\n\n"
            f"Usage:\n"
            f"  python interceptor.py <mcp-server-command> [args...]\n\n"
            f"Examples:\n"
            f"  python interceptor.py npx -y @modelcontextprotocol/server-filesystem /tmp\n"
            f"  python interceptor.py python my_server.py\n"
            f"  python interceptor.py node dist/index.js\n\n"
            f"Then point Claude Desktop or Cursor at this script instead of the server.\n"
        )
        sys.exit(1)

    server_cmd = sys.argv[1:]

    try:
        asyncio.run(run_proxy(server_cmd))
    except KeyboardInterrupt:
        render_summary()
