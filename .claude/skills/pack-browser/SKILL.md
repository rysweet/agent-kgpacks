---
name: pack-browser
description: Browse, search, and install knowledge packs into your local environment
triggers:
  - list available packs
  - show packs
  - what packs are available
  - install pack *
  - add the * pack
  - search packs for *
  - find packs about *
  - browse packs
  - pack browser
---

# Pack Browser Skill

Browse, search, and install knowledge packs from the wikigr pack registry. Each
pack is a self-contained knowledge graph database covering a specific domain
(programming language, framework, technology) with eval questions for quality
validation.

## How to Use

When the user asks about available packs, searching for packs, or installing
packs, use the CLI tool at `scripts/install_pack.py` in the project root.

### List All Packs

Run:

```bash
uv run python scripts/install_pack.py list
```

Options: `--sort name|size|articles`

Present the output as a formatted table showing pack name, article count, size,
eval accuracy, and a short description.

### Search Packs

Run:

```bash
uv run python scripts/install_pack.py search <keyword>
```

This searches pack names, descriptions, and tags. Example keywords: kubernetes,
rust, azure, security, graph.

### Show Pack Details

Run:

```bash
uv run python scripts/install_pack.py info <pack-name>
```

Shows full metadata: description, article count, size, eval scores, tags,
license, and download URL.

### Install a Pack

Run:

```bash
uv run python scripts/install_pack.py install <pack-name>
```

Options: `--target <directory>` to install to a custom location (default:
`~/.wikigr/packs/`).

The installer tries to copy from the local `data/packs/` directory first. If the
pack is not available locally, it downloads from the GitHub releases URL in the
registry.

After installation, tell the user where the pack was installed and suggest they
can use it with the KG Agent or load the pack.db directly.

### Regenerate the Registry

If packs have been added or updated, regenerate the registry:

```bash
uv run python scripts/generate_pack_registry.py
```

This scans all `data/packs/*/manifest.json` files and writes
`data/pack_registry.json`.

## Output Formatting

When presenting pack listings to the user, format as a table:

```
| Pack                    | Articles | Size   | Eval | Description                              |
|-------------------------|----------|--------|------|------------------------------------------|
| kubernetes-networking   |      150 | 28 MB  |  n/a | K8s networking - CNI, service mesh, ...  |
| physics-expert          |      451 | 80 MB  |  n/a | Classical mechanics, quantum, relativity |
| rust-expert             |      294 | 40 MB  |  n/a | Ownership, traits, async, unsafe code    |
```

For the `info` command, present details in a clean key-value format.

## Pack Registry Format

The registry at `data/pack_registry.json` contains:

```json
{
  "generated_at": "2026-02-28T...",
  "pack_count": 25,
  "packs": [
    {
      "name": "kubernetes-networking",
      "description": "...",
      "version": "1.0.0",
      "articles": 150,
      "size_mb": 28.0,
      "tags": ["kubernetes", "networking"],
      "has_eval": true,
      "license": "MIT",
      "download_url": "https://github.com/rysweet/agent-kgpacks/releases/download/v1/kubernetes-networking.tar.gz"
    }
  ]
}
```

## Notes

- Packs with 0 articles are stub manifests (seed definitions not yet built)
- The `eval_accuracy` field is only present for packs that have been evaluated
- All packs include a pack.db (Kuzu graph database) and optionally eval questions
- The default install location `~/.wikigr/packs/` is where the KG Agent looks for packs
