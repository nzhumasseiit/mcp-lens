# mcp-trace

stdio proxy for MCP servers. wraps any MCP server and shows every 
tool call, latency and failure live in terminal.

no dependencies. no code changes needed.

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

## why

official MCP inspector = postman (manual testing)
mcp-trace = sentry (live production monitoring)

when your agent breaks at 2am you shouldn't be reading mcp.log
