"""
MCP Server for agent-kgpacks — exposes knowledge pack queries to MCP clients.

Run:
    uv run python mcp_server.py

Configure in VS Code (settings.json) for GitHub Copilot:
    {
      "mcp": {
        "servers": {
          "kgpacks": {
            "command": "uv",
            "args": ["run", "python", "mcp_server.py"],
            "cwd": "/path/to/agent-kgpacks"
          }
        }
      }
    }

Configure for Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "kgpacks": {
          "command": "uv",
          "args": ["run", "python", "mcp_server.py"],
          "cwd": "/path/to/agent-kgpacks"
        }
      }
    }
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

PACKS_DIR = Path(__file__).parent / "data" / "packs"

mcp = FastMCP(
    name="agent-kgpacks",
    instructions=(
        "Knowledge-pack query server. Use list_packs to discover available packs, "
        "pack_info to inspect a specific pack, and query_knowledge_pack to ask "
        "questions against a pack's knowledge graph."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_pack_dir(pack_name: str) -> Path:
    """Resolve and validate a pack directory."""
    pack_dir = PACKS_DIR / pack_name
    if not pack_dir.is_dir():
        raise ValueError(
            f"Pack '{pack_name}' not found. " f"Use list_packs() to see available packs."
        )
    return pack_dir


def _load_manifest(pack_dir: Path) -> dict:
    """Load manifest.json from a pack directory."""
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        return {"name": pack_dir.name, "error": "manifest.json missing"}
    return json.loads(manifest_path.read_text())


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_packs() -> str:
    """List all available knowledge packs with article counts.

    Returns a JSON array of objects with name, description, and article_count
    for every pack found under data/packs/.
    """
    packs: list[dict] = []
    if not PACKS_DIR.is_dir():
        return json.dumps({"error": "Packs directory not found", "path": str(PACKS_DIR)})

    for pack_dir in sorted(PACKS_DIR.iterdir()):
        if not pack_dir.is_dir():
            continue
        manifest = _load_manifest(pack_dir)
        packs.append(
            {
                "name": manifest.get("name", pack_dir.name),
                "description": manifest.get("description", ""),
                "article_count": manifest.get("graph_stats", {}).get("articles", 0),
            }
        )
    return json.dumps(packs, indent=2)


@mcp.tool()
def pack_info(pack_name: str) -> str:
    """Return full manifest details for a specific knowledge pack.

    Args:
        pack_name: Directory name of the pack (e.g. 'python-expert').
    """
    pack_dir = _get_pack_dir(pack_name)
    manifest = _load_manifest(pack_dir)
    # Add computed fields
    manifest["db_exists"] = (pack_dir / "pack.db").exists()
    manifest["urls_file_exists"] = (pack_dir / "urls.txt").exists()
    return json.dumps(manifest, indent=2)


@mcp.tool()
def query_knowledge_pack(
    pack_name: str,
    question: str,
    max_results: int = 5,
) -> str:
    """Query a knowledge pack's graph and return an answer with sources.

    Uses the KnowledgeGraphAgent to perform vector + graph search over the
    pack's LadybugDB database and synthesize a natural-language answer.

    Args:
        pack_name: Directory name of the pack (e.g. 'python-expert').
        question: Natural language question to answer.
        max_results: Maximum number of graph results to retrieve (1-1000).
    """
    pack_dir = _get_pack_dir(pack_name)
    db_path = pack_dir / "pack.db"
    if not db_path.exists():
        return json.dumps({"error": f"Database not found at {db_path}"})

    # Import here to avoid heavy imports when only listing packs.
    from wikigr.agent.kg_agent import KnowledgeGraphAgent

    try:
        with KnowledgeGraphAgent(
            db_path=str(db_path),
            read_only=True,
            use_enhancements=False,
        ) as agent:
            result = agent.query(question, max_results=max_results)
    except Exception as exc:
        logger.exception("Query failed for pack '%s'", pack_name)
        return json.dumps({"error": str(exc), "pack": pack_name})

    # Return the agent result directly — it already has answer, sources, etc.
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
