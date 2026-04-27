from __future__ import annotations

"""Continue / operator bridge: the graph is exposed via the MCP stdio server in ``mcp_server``.

Example **Continue** (`.continue/config.json`) server entry — adjust the venv path:

```json
{
  "mcpServers": {
    "heart-transplant": {
      "command": "/abs/path/to/backend/.venv/bin/python",
      "args": ["-m", "heart_transplant.mcp_server"],
      "env": {
        "HEART_TRANSPLANT_SURREAL_URL": "ws://127.0.0.1:8000",
        "HEART_TRANSPLANT_SURREAL_NS": "ht",
        "HEART_TRANSPLANT_SURREAL_DB": "graph"
      }
    }
  }
}
```

The same stdio block works in **Cursor** MCP settings. Start Surreal, run ``load-surreal`` on an artifact, then start this server.
"""

CONTINUE_MCP_CONFIG_SNIPPET = """
{
  "mcpServers": {
    "heart-transplant": {
      "command": "python",
      "args": ["-m", "heart_transplant.mcp_server"],
      "env": {
        "HEART_TRANSPLANT_SURREAL_URL": "ws://127.0.0.1:8000"
      }
    }
  }
}
""".strip()
