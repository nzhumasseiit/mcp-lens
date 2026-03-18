# mcp-lens

zero-dependency single-file Python proxy for MCP servers.

wraps any MCP server, shows every tool call, latency and failure live in terminal.

no dependencies. no code changes needed. just python3.

## usage

instead of running your MCP server directly, wrap it:
```bash
python3 interceptor.py npx -y @modelcontextprotocol/server-filesystem /tmp
python3 interceptor.py node your-server.js
python3 interceptor.py python your-server.py
```

point claude desktop at it in claude_desktop_config.json:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "python3",
      "args": ["/path/to/interceptor.py", "npx", "-y", 
               "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  }
}
```

## troubleshooting (Claude Desktop crashes / can't connect)

- **Use absolute paths**: Claude Desktop often runs with a minimal `PATH`, so `"python3"` and `"npx"` may not be found.
  - Find paths:
    - `which python3`
    - `which npx`
- **Use a modern Python**: `python3.9+` recommended.
- **Sanity check in Terminal** (same user account as Claude):

```bash
/ABS/PATH/TO/python3 /ABS/PATH/TO/interceptor.py /ABS/PATH/TO/npx -y @modelcontextprotocol/server-filesystem /tmp
```

Then paste that same absolute-path command into `claude_desktop_config.json`.

## why

official MCP inspector = postman (manual testing)
mcp-trace = sentry (live production monitoring)

when your agent breaks at 2am you shouldn't be reading mcp.log
