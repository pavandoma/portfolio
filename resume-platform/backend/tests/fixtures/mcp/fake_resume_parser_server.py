"""A tiny local MCP server used only by tests (stands in for an external resume parser).

It extracts an email and counts words; it is not a real resume parser or matcher.
"""

import re

from mcp.server.mcpserver import MCPServer

server = MCPServer("fake-resume-parser")


@server.tool()
def parse_resume(resume_text: str) -> dict:
    """Return a few fields extracted from resume text."""
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", resume_text)
    return {"email": email.group(0) if email else None, "word_count": len(resume_text.split()), "score": 77.5}


@server.tool()
def broken_tool(resume_text: str) -> dict:
    """Always fails."""
    raise ValueError("simulated failure")


if __name__ == "__main__":
    server.run()
