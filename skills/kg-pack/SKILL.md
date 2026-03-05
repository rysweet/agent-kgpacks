---
name: kg-pack
description: "Knowledge graph pack manager. Build, install, list, query, and update domain-expert knowledge packs. Use when user says /kg-pack or wants to add expert knowledge to Claude Code."
user-invocable: true
---

# Knowledge Graph Pack Manager

Build, install, and manage domain-expert knowledge packs that give Claude
deep expertise in specific technologies, frameworks, and languages.

Each pack is a LadybugDB graph database containing extracted documentation
with vector embeddings for semantic search, entity relationships, and facts.

## Setup

This skill requires the `agent-kgpacks` repository. If not present:

```bash
# Clone the repo (if not already available)
git clone https://github.com/rysweet/agent-kgpacks.git ~/.wikigr/agent-kgpacks
cd ~/.wikigr/agent-kgpacks && uv sync
```

Set `KGPACKS_ROOT` to the repo location (defaults to `~/.wikigr/agent-kgpacks`):

```bash
export KGPACKS_ROOT=~/.wikigr/agent-kgpacks
```

## Commands

Parse the user's arguments to determine the subcommand:

| Command | Example | What it does |
|---------|---------|-------------|
| `list` | `/kg-pack list` | Show all available and installed packs |
| `install <name>` | `/kg-pack install rust-expert` | Install a pack as a Claude Code skill in this project |
| `build <topic>` | `/kg-pack build "kubernetes networking"` | Build a new pack from a topic |
| `build-from-urls <file>` | `/kg-pack build-from-urls urls.md` | Build a pack from a URL list |
| `query <pack> <question>` | `/kg-pack query rust-expert "how do lifetimes work?"` | Query a pack's knowledge graph |
| `update <name>` | `/kg-pack update rust-expert` | Rebuild a pack with latest docs |
| `info <name>` | `/kg-pack info rust-expert` | Show pack details |
| `uninstall <name>` | `/kg-pack uninstall rust-expert` | Remove a pack's skill from this project |

## Execution

### `list`

```bash
KGPACKS_ROOT="${KGPACKS_ROOT:-$HOME/.wikigr/agent-kgpacks}"
for db in "$KGPACKS_ROOT"/data/packs/*/pack.db; do
  dir=$(dirname "$db"); name=$(basename "$dir")
  articles=$(python3 -c "import json; print(json.load(open('$dir/manifest.json')).get('graph_stats',{}).get('articles','?'))" 2>/dev/null)
  installed="no"; [ -f ".claude/skills/$name/SKILL.md" ] && installed="yes"
  printf "%-30s %4s articles  installed=%s\n" "$name" "$articles" "$installed"
done | sort
```

### `install <name>`

1. Verify pack exists at `$KGPACKS_ROOT/data/packs/{name}/pack.db`
2. Generate and write SKILL.md to `.claude/skills/{name}/SKILL.md` in the current project
3. The skill tells Claude how to query that pack's KG when the domain comes up

```bash
KGPACKS_ROOT="${KGPACKS_ROOT:-$HOME/.wikigr/agent-kgpacks}"
cd "$KGPACKS_ROOT" && uv run python scripts/install_pack_skills.py
# Or install a single pack:
mkdir -p .claude/skills/{name}
# Generate SKILL.md with pack-specific content (see install_pack_skills.py)
```

### `build <topic>`

1. Normalize topic → pack name (lowercase, hyphens)
2. Use WebSearch to find 30-50 documentation URLs
3. Create `$KGPACKS_ROOT/data/packs/{name}/urls.txt`
4. Run build:

```bash
cd "$KGPACKS_ROOT"
uv run python scripts/build_pack_from_issue.py --issue-json '{
  "pack_name": "{name}",
  "description": "{topic}",
  "search_terms": "{search terms}"
}'
```

5. Install skill: `uv run python scripts/install_pack_skills.py`

### `query <pack> <question>`

```python
import sys
sys.path.insert(0, KGPACKS_ROOT)
from wikigr.agent.kg_agent import KnowledgeGraphAgent

with KnowledgeGraphAgent(
    db_path=f"{KGPACKS_ROOT}/data/packs/{pack_name}/pack.db",
    read_only=True
) as agent:
    result = agent.query(question, max_results=5)
    # Use result["answer"], result["sources"], result["entities"]
```

### `info <name>`

Read and display `$KGPACKS_ROOT/data/packs/{name}/manifest.json`.

### `update <name>`

Delete `pack.db`, re-run build script, re-install skill.

### `uninstall <name>`

```bash
rm -rf .claude/skills/{name}
```

## Notes

- Builds require `ANTHROPIC_API_KEY` and take 3-30 minutes
- Pack databases (pack.db) are 2-50 MB, built locally
- Skills activate in the next Claude Code session, not the current one
- Run `/kg-pack list` to see what's available before installing
