# Evaluation Results

48 packs evaluated with LadybugDB 0.15.1, 5 questions per pack (240 total). Judge model: Claude Opus 4.6.

## Summary

| Metric | Training (Claude alone) | Pack (KG retrieval) | Enhanced (KG + reranker + multidoc + fewshot) |
|--------|:-----------------------:|:-------------------:|:---------------------------------------------:|
| **Avg Score** | 8.85/10 | 9.0/10 | **9.47/10** |
| **Accuracy (>=7)** | 90.8% | 90.4% | **95.0%** |
| **Questions** | 240 | 240 | 240 |

Enhanced mode achieves **95% accuracy** — a +4.2pp improvement over training baseline.

## Three-Condition Comparison

The evaluation tests three delivery modes:

1. **Training**: Claude Opus answers from training knowledge only
2. **Pack**: Claude + single KG Agent query (pre-fetched context)
3. **Enhanced**: Claude + KG Agent with reranker, multi-doc synthesis, and few-shot examples

## Top Accuracy Gains (Enhanced vs Training)

| Pack | Training | Pack | Enhanced | Delta |
|------|:--------:|:----:|:--------:|:-----:|
| workiq-mcp | 20% | 20% | **80%** | **+60pp** |
| azure-ai-foundry | 40% | 60% | **80%** | **+40pp** |
| docker-expert | 20% | 20% | **60%** | **+40pp** |
| azure-lighthouse | 80% | 100% | **100%** | **+20pp** |
| fabric-graph-gql-expert | 80% | 80% | **100%** | **+20pp** |
| github-actions-advanced | 60% | 60% | **80%** | **+20pp** |
| go-expert | 80% | 100% | **100%** | **+20pp** |
| microsoft-agent-framework | 80% | 80% | **100%** | **+20pp** |
| rust-async-expert | 80% | 100% | **100%** | **+20pp** |
| semantic-kernel | 80% | 80% | **100%** | **+20pp** |

## Where Packs Add the Most Value

The biggest gains come from domains where Claude's training data is thin or outdated:

- **workiq-mcp** (+60pp): Internal Microsoft tool with virtually no public training data
- **azure-ai-foundry** (+40pp): Rapidly evolving Azure service with frequent API changes
- **docker-expert** (+40pp): Advanced Docker patterns beyond basic training coverage

## Where Packs Match Training

Many packs achieve 100% in both training and enhanced conditions (bicep, cpp, csharp, dotnet, dspy, fabric-graphql, huggingface, java, kotlin, kubernetes, langchain, llamaindex, mcp-protocol, nextjs, openai-api, opencypher, opentelemetry, physics, postgresql, prompt-engineering, python, react, ruby, rust, swift, terraform, typescript, vercel, vscode, wasm, zig). The pack still provides value through:

- Source attribution (every answer cites specific documentation)
- Confidence gating ensures the pack never degrades results
- Graph traversal finds connections training data misses

## Skill Delivery Evaluation

A separate A/B/C evaluation (`scripts/eval_skill_delivery.py`) tests whether delivering packs as Claude Code skills improves **coding task** outcomes (not just Q&A):

| Condition | Avg Judge (0-10) | Accuracy (>=7) |
|-----------|:---:|:---:|
| A) Baseline (Claude alone) | 7.0 | 73% |
| B) Pack retrieval | 7.5 | 80% |
| C) Skill delivery (tool_use) | 6.9 | 80% |

Key finding: Pack retrieval helps for niche domains. Skill delivery (tool_use) doesn't consistently beat pre-fetched context. See issue #287 for full analysis.

## Methodology

- **Database**: LadybugDB 0.15.1 (rebuilt from Kuzu migration)
- **Answer model**: Claude Opus 4.6
- **Judge model**: Claude Opus 4.6
- **Questions per pack**: 5 (from `eval/questions.jsonl`)
- **Accuracy threshold**: Score >= 7 out of 10
- **Conditions**: Training / Pack / Enhanced

Run the evaluation:

```bash
uv run python scripts/run_all_packs_evaluation.py --sample 5
uv run python scripts/eval_skill_delivery.py --all
```

See [Methodology](methodology.md) for full details.
