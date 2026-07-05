# Connecting to Engram over MCP

Engram exposes its memory as MCP tools: `engram_recall`, `engram_store`,
`engram_report_outcome`, `engram_list`. Any MCP client inherits the same
memory.

## Claude Code

Local (stdio):

```bash
claude mcp add engram -- /path/to/engram/.venv/bin/python -m engram.server.mcp_server
```

Remote (SSE, e.g. the ECS deployment):

```bash
claude mcp add --transport sse engram-remote http://<ECS_IP>:8765/sse
```

## Cursor

`~/.cursor/mcp.json` (or project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "engram": {
      "command": "/path/to/engram/.venv/bin/python",
      "args": ["-m", "engram.server.mcp_server"]
    },
    "engram-remote": {
      "url": "http://<ECS_IP>:8765/sse"
    }
  }
}
```

## Running the SSE server

```bash
make serve-mcp   # SSE on 0.0.0.0:8765
```

## Smoke test

Ask your MCP client: *"Use engram_list to show stored memories."*
