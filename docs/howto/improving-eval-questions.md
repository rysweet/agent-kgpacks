# Improving Eval Questions for Knowledge Packs

How to audit, correct, and improve evaluation questions to ensure they accurately measure pack-specific knowledge rather than general model training.

## Problem: Training Data Overlap

When a pack's evaluation score for the base model (no pack) approaches or matches the pack-augmented score, the questions are likely testing knowledge already present in the model's training data. This defeats the purpose of evaluation, which is to measure what the *pack adds*.

**Symptoms of poor eval questions:**

- Pack training score ≈ base model score (e.g., `training: 100%`, `pack: 94%`)
- Questions use generic terminology instead of library-specific APIs
- Ground truth references deprecated APIs that the model confidently "knows"
- Questions about removed language features that appear in older training data

## Audit Checklist

Before modifying questions, run this checklist per pack:

1. **Scope check**: Does each question reference a concept covered in the pack's `urls.txt`?
2. **Terminology check**: Does the question use the exact casing and naming from the official docs (e.g., `VectorStoreIndex` not `vector store index`)?
3. **Currency check**: Is the ground truth correct for the current version of the library/language?
4. **Specificity check**: Would a model with no pack access likely answer this correctly from training data alone?
5. **Difficulty distribution**: Does the difficulty tag (`easy`/`medium`/`hard`) match the question's actual difficulty against a base model?

## JSONL Format

Every question must be a valid JSON object on a single line with exactly six fields:

```json
{"id": "pk_NNN", "domain": "pack_domain", "difficulty": "easy|medium|hard", "question": "...", "ground_truth": "...", "source": "source_topic_key"}
```

| Field | Description |
|-------|-------------|
| `id` | Pack prefix + zero-padded number (`ge_009`, `re_001`) |
| `domain` | Snake-case domain identifier (`go_expert`, `react_expert`) |
| `difficulty` | One of `easy`, `medium`, `hard` |
| `question` | The question text posed to the model |
| `ground_truth` | Expected answer used for evaluation comparison |
| `source` | Slug identifying the source topic within the pack |

**Required distribution** (50-question packs): 20 easy / 20 medium / 10 hard.
**Required distribution** (51-question packs, e.g., langchain, bicep): 20 easy / 20 medium / 11 hard.

## Common Fixes Applied in Issue 211

### Fix 1: Replace Training-Data Questions With Pack-Specific Ones

**Applies to**: go-expert, react-expert

When training scores are 100% and pack scores are near-identical, easy questions are likely testing general knowledge. Replace easy questions with the newest, least-trained content.

**go-expert example** — replaced generic concurrency questions with Go 1.21–1.23 stdlib additions:

| Old (generic) | New (pack-specific) |
|---------------|---------------------|
| What is a goroutine? | What does `slices.Contains` do, and what constraint must E satisfy? |
| How do channels work? | What is `iter.Seq[V any]` and what is its underlying function signature? |
| What is `sync.WaitGroup`? | What major change does `math/rand/v2` make vs `math/rand`? |

**Replaced IDs**: `ge_009`, `ge_010`, `ge_011`, `ge_012`, `ge_019`, `ge_020`

**react-expert example** — replaced all 20 easy questions ("React Expert system" questions) with React 19+ features:

New topics include: `"use client"` directive, `"use server"` / Server Actions, `use()` hook, `useFormStatus`, `useOptimistic`, Document Metadata API, Asset Loading APIs, ref-as-prop, `useActionState`, React Server Components, client boundaries, `cache()`, Suspense+RSC, Context provider syntax changes, `startTransition`, ref cleanup functions, `prefetchDNS`, hydration error improvements, taint API.

**Replaced IDs**: `re_001` through `re_020`

### Fix 2: Update Deprecated API References in Ground Truth

**Applies to**: langchain-expert, openai-api-expert

Ground truth must reflect the *current* state of the API, not a historical snapshot.

**langchain-expert** — LangServe is soft-deprecated; ground truth now mentions LangGraph Platform as the recommended successor:

```json
{
  "id": "le_015",
  "ground_truth": "LangServe is a deployment tool ... However, LangServe is soft-deprecated; LangGraph Platform is the recommended successor for new production deployments. LangGraph Platform offers native support for stateful agents, human-in-the-loop interrupts, streaming, and better scalability for LangGraph-based applications."
}
```

**Affected IDs**: `le_015`, `le_035`

**openai-api-expert** — deprecated model names replaced with current ones:

| Old reference | New reference |
|---------------|---------------|
| `gpt-4-turbo` | `gpt-4o` |
| `gpt-3.5-turbo` | `gpt-4o-mini` |
| — | `o1`, `o3` (reasoning models) |

**Affected IDs**: `oa_009`, `oa_034`

*o-series token parameter corrected* (`oa_004`): o-series reasoning models require `max_completion_tokens` instead of `max_tokens`, because `max_completion_tokens` covers both visible output tokens and internal reasoning tokens. This is a separate correction from the model-name updates above.

**Affected ID**: `oa_004`

### Fix 3: Add Questions for New API Surface

**Applies to**: openai-api-expert

When a major new API has been released since questions were generated, add dedicated questions. The Responses API (`/v1/responses`) is a fundamentally different interface from Chat Completions and warrants distinct coverage.

Three Responses API questions were added:

| ID | Difficulty | Topic |
|----|------------|-------|
| `oa_002` | easy | `/v1/responses` endpoint path and differences from Chat Completions |
| `oa_038` | medium | `previous_response_id` for stateful multi-turn conversations |
| `oa_044` | hard | Built-in tools (`web_search_preview`, `file_search`, `code_interpreter`) vs custom function calling |

### Fix 4: Correct Factually Wrong Ground Truth

**Applies to**: vercel-ai-sdk, bicep-infrastructure

Ground truth that is factually incorrect will always penalize the model unfairly (or reward it for reproducing the error).

**vercel-ai-sdk** — two distinct corrections:

*Incorrect WebSocket claim removed* (`va_017`, `va_034`):

```json
{
  "id": "va_017",
  "ground_truth": "The Vercel AI SDK uses two HTTP-based streaming protocols: Server-Sent Events (SSE) for broad compatibility, and the AI Data Stream Protocol ... WebSocket-based streaming is not natively supported by the SDK."
}
```

Both `va_017` and `va_034` previously claimed WebSocket support. Both now correctly state that only SSE and the AI Data Stream Protocol are supported (HTTP-based, unidirectional).

*`maxSteps` role clarified* (`va_007`): ground truth now explicitly identifies `maxSteps` as the *primary* step-limit parameter and `stopWhen` as a complementary predicate for dynamic termination.

**Affected IDs**: `va_007`, `va_017`, `va_034`

**bicep-infrastructure** — wrong Key Vault reference syntax:

```json
{
  "id": "bi_011",
  "ground_truth": "In a `.bicepparam` file, use the `az.getSecret()` function: `param mySecret = az.getSecret('<subscriptionId>', '<resourceGroupName>', '<keyVaultName>', '<secretName>')`. This Bicep-native syntax retrieves the secret at deployment time. The older `@Microsoft.KeyVault(...)` inline syntax applies to ARM JSON parameter files, not `.bicepparam` files."
}
```

**Affected IDs**: `bi_011`

### Fix 5: Remove Questions About Removed Language Features

**Applies to**: zig-expert

When a language version removes a feature (Zig 0.12 removed `async`/`await`), questions about that feature test obsolete knowledge and may confuse the model with conflicting training data.

Three async I/O questions were replaced:

| Removed topic | Replacement topic | ID |
|---------------|-------------------|----|
| Zig async I/O | `GeneralPurposeAllocator` leak detection | `ze_019` |
| Zig async frame scheduling | Zig 0.13 `b.dependency()` / `addImport` build API | `ze_040` |
| Zig async/await suspension | `anytype` comptime duck-typing interfaces | `ze_048` |

## Validation After Editing

After modifying any `questions.jsonl`, run structural and content validation:

```bash
# 1. Validate JSONL parses cleanly
python -c "
import json, sys
path = 'data/packs/PACK/eval/questions.jsonl'
lines = open(path).readlines()
for i, line in enumerate(lines, 1):
    obj = json.loads(line)
    required = {'id','domain','difficulty','question','ground_truth','source'}
    missing = required - obj.keys()
    if missing:
        print(f'Line {i}: missing fields {missing}')
        sys.exit(1)
print(f'OK: {len(lines)} questions, all valid')
"

# 2. Check difficulty distribution
python -c "
import json
from collections import Counter
lines = open('data/packs/PACK/eval/questions.jsonl').readlines()
counts = Counter(json.loads(l)['difficulty'] for l in lines)
print(counts)  # expect {'easy': 20, 'medium': 20, 'hard': 10}
"

# 3. Content guards — customize per pack
# zig-expert: no async/await references
grep -i "async\|await" data/packs/zig-expert/eval/questions.jsonl && echo FAIL || echo OK

# react-expert: no 'React Expert' system references in easy questions
python -c "
import json
bad = [json.loads(l) for l in open('data/packs/react-expert/eval/questions.jsonl')
       if json.loads(l)['difficulty']=='easy' and 'React Expert' in json.loads(l).get('ground_truth','')]
print('FAIL:', bad) if bad else print('OK')
"

# openai-api-expert: Responses API coverage
grep -c 'responses_api' data/packs/openai-api-expert/eval/questions.jsonl
# expect >= 3

# openai-api-expert: no deprecated model names
grep -i 'gpt-4-turbo\|gpt-3\.5-turbo' data/packs/openai-api-expert/eval/questions.jsonl && echo FAIL || echo OK

# bicep: correct Key Vault syntax
grep 'az\.getSecret' data/packs/bicep-infrastructure/eval/questions.jsonl | grep bi_011 || echo MISSING

# langchain: LangGraph mentioned as successor
grep 'LangGraph Platform' data/packs/langchain-expert/eval/questions.jsonl | wc -l
# expect >= 2
```

## Decisions and Trade-offs

### When a Pack Needs No Changes

If terminology is already correct and all questions reference content from `urls.txt`, no changes are needed. Verified with llamaindex-expert: `VectorStoreIndex`, `SummaryIndex`, `AgentWorkflow`, and `Workflows` were all correctly cased — no edits were made.

### Replacing Easy Questions Raises Difficulty

Questions targeting new framework features (React 19, Go 1.23, Zig 0.13) will be harder for a base model than the generic questions they replace. This is intentional: the point of easy pack questions is to test things the pack teaches, not things the model already knows. If the difficulty tag feels wrong after replacement, adjust accordingly.

### Source Field Naming

The `source` field is a slug identifying the topic origin. When replacing a question that covered a different topic, update the source slug to reflect the new topic:

```json
// Old (topic: async_io)
{"id": "ze_019", "source": "async_io", ...}

// New (topic: general_purpose_allocator)
{"id": "ze_019", "source": "general_purpose_allocator", ...}
```

### ID Prefix Collisions Across Packs

llamaindex-expert and langchain-expert both use `le_` prefixes. This is a pre-existing naming collision. Since packs are evaluated in isolated contexts, there is no runtime conflict. Do not renumber existing IDs to resolve it.

## See Also

- [Generating Evaluation Questions](generating-evaluation-questions.md) — generating questions from scratch for new packs
- [Pack Content Quality](dotnet-content-quality.md) — fixing thin content before evaluation
- [Vector Search Retrieval](vector-search-primary-retrieval.md) — retrieval pipeline improvements
