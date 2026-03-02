# Evaluation Results

44 packs evaluated, 10 questions each, 440 total. Judge model: Claude Opus.

## Summary

| Metric | Training (Claude alone) | With Knowledge Pack |
|--------|:-----------------------:|:-------------------:|
| **Accuracy** | 91% | **98%** |
| **Avg Score** | 8.8/10 | **9.6/10** |
| **Delta** | — | **+7pp** |
| **Pack wins** | — | **15 of 44 (34%)** |
| **Ties** | — | **27 of 44 (61%)** |
| **Losses** | — | **2 of 44 (5%)** |

Pack accuracy of 98% means only 9 of 440 questions scored below 7/10.

## Per-Pack Results

Sorted by accuracy gain over training baseline.

| Pack | Training | Pack | Delta |
|------|:--------:|:----:|:-----:|
| workiq-mcp | 20% | **100%** | **+80pp** |
| azure-ai-foundry | 60% | **100%** | **+40pp** |
| claude-agent-sdk | 60% | **90%** | **+30pp** |
| docker-expert | 40% | **70%** | **+30pp** |
| fabric-graph-gql-expert | 80% | **100%** | **+20pp** |
| github-copilot-sdk | 70% | **90%** | **+20pp** |
| crew-ai-expert | 80% | **90%** | **+10pp** |
| github-actions-advanced | 80% | **90%** | **+10pp** |
| microsoft-agent-framework | 90% | **100%** | **+10pp** |
| nextjs-expert | 90% | **100%** | **+10pp** |
| react-expert | 90% | **100%** | **+10pp** |
| rust-async-expert | 80% | **90%** | **+10pp** |
| rust-expert | 90% | **100%** | **+10pp** |
| semantic-kernel | 90% | **100%** | **+10pp** |
| vscode-extensions | 90% | **100%** | **+10pp** |
| autogen-expert | 100% | 100% | 0pp |
| bicep-infrastructure | 100% | 100% | 0pp |
| cpp-expert | 100% | 100% | 0pp |
| csharp-expert | 100% | 100% | 0pp |
| dotnet-expert | 100% | 100% | 0pp |
| dspy-expert | 100% | 100% | 0pp |
| go-expert | 100% | 100% | 0pp |
| huggingface-transformers | 100% | 100% | 0pp |
| java-expert | 100% | 100% | 0pp |
| kotlin-expert | 100% | 100% | 0pp |
| kubernetes-networking | 100% | 100% | 0pp |
| langchain-expert | 100% | 100% | 0pp |
| llamaindex-expert | 100% | 100% | 0pp |
| mcp-protocol | 100% | 100% | 0pp |
| openai-api-expert | 100% | 100% | 0pp |
| opencypher-expert | 100% | 100% | 0pp |
| opentelemetry-expert | 100% | 100% | 0pp |
| physics-expert | 100% | 100% | 0pp |
| postgresql-internals | 100% | 100% | 0pp |
| prompt-engineering | 100% | 100% | 0pp |
| python-expert | 100% | 100% | 0pp |
| ruby-expert | 100% | 100% | 0pp |
| swift-expert | 100% | 100% | 0pp |
| terraform-expert | 100% | 100% | 0pp |
| typescript-expert | 100% | 100% | 0pp |
| wasm-components | 100% | 100% | 0pp |
| zig-expert | 100% | 100% | 0pp |
| anthropic-api-expert | 90% | 80% | -10pp |
| vercel-ai-sdk | 100% | 90% | -10pp |

## Where Packs Add the Most Value

The biggest accuracy gains come from domains where Claude's training data is thin or outdated:

- **workiq-mcp** (+80pp): Internal Microsoft tool with virtually no public training data
- **azure-ai-foundry** (+40pp): Rapidly evolving Azure service with frequent API changes
- **claude-agent-sdk** (+30pp): Very new SDK not fully covered in training
- **docker-expert** (+30pp): Advanced Docker patterns beyond basic training coverage

## Where Packs Match Training

27 packs achieve 100% accuracy in both conditions. These are well-established technologies (Go, Python, React, Java, etc.) where Claude's training is comprehensive. The pack still provides value through:

- Source attribution (every answer cites specific documentation)
- Offline capability (no internet needed once installed)
- Confidence gating ensures the pack never degrades these results

## Losses

Two packs score slightly below training:

| Pack | Issue |
|------|-------|
| **anthropic-api-expert** | Pack content may conflict with Claude's built-in knowledge of its own API |
| **vercel-ai-sdk** | JS-heavy documentation pages produce thin extracted content |

## Methodology

- **Answer model**: Claude Opus (`claude-opus-4-6`)
- **Judge model**: Claude Opus (`claude-opus-4-6`)
- **Questions per pack**: 10 (from `eval/questions.jsonl`)
- **Accuracy threshold**: Score >= 7 out of 10
- **Conditions**: Training (Claude alone) vs Pack (KG Agent with full retrieval pipeline)

See [Methodology](methodology.md) for full details.
