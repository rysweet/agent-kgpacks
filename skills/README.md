# Knowledge Pack Skills for Claude Code

## Quick Start

Install the `/kg-pack` command in any Claude Code project:

```bash
# Copy the skill to your project
mkdir -p .claude/skills/kg-pack
cp /path/to/agent-kgpacks/skills/kg-pack/SKILL.md .claude/skills/kg-pack/SKILL.md
```

Or set up the full system:

```bash
# Clone the repo
git clone https://github.com/rysweet/agent-kgpacks.git ~/.wikigr/agent-kgpacks
cd ~/.wikigr/agent-kgpacks && uv sync

# Install the /kg-pack command in your project
mkdir -p /your/project/.claude/skills/kg-pack
cp ~/.wikigr/agent-kgpacks/skills/kg-pack/SKILL.md /your/project/.claude/skills/kg-pack/

# Install domain-expert skills (49 available)
cd ~/.wikigr/agent-kgpacks && uv run python scripts/install_pack_skills.py
```

## Usage

In any Claude Code session:

```
/kg-pack list                              # See all available packs
/kg-pack install rust-expert               # Install Rust expertise
/kg-pack build "WebAssembly components"    # Build a new pack
/kg-pack query rust-expert "how do traits work?"  # Query directly
```

## Available Packs

49 domain-expert packs covering languages, frameworks, and tools:

| Category | Packs |
|----------|-------|
| **Languages** | rust, python, go, java, kotlin, csharp, cpp, ruby, swift, typescript, zig |
| **AI/ML** | anthropic-api, openai-api, claude-agent-sdk, langchain, llamaindex, huggingface-transformers, dspy, crew-ai, autogen, microsoft-agent-framework, semantic-kernel |
| **Web** | react, nextjs, vercel-ai-sdk, vscode-extensions |
| **Infrastructure** | docker, kubernetes-networking, terraform, bicep-infrastructure, github-actions-advanced |
| **Databases** | ladybugdb, postgresql-internals, opencypher |
| **Azure** | azure-ai-foundry, azure-lighthouse, fabric, fabric-graphql, security-copilot, sentinel-graph, workiq-mcp |
| **Other** | mcp-protocol, github-copilot-sdk, opentelemetry, prompt-engineering, wasm-components, physics, rust-async, dotnet |
