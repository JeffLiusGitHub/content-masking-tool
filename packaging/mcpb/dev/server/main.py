"""Dev-build entry: runs the MCP server from the project venv.

The .mcpb manifest points Claude Desktop's spawn command at the project
venv's python.exe with this file as the argument, so the tool runs against
the live editable install (no freeze needed while developing).
"""
from maskingtool.mcp_server.server import main

if __name__ == "__main__":
    main()
