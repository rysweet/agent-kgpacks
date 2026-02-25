# Physics-Expert Pack Evaluation Tests

This directory contains comprehensive TDD tests for the physics-expert knowledge pack evaluation system.

## Test Files

### Unit Tests (60% of total)
- `test_question_schema.py` - Question set validation (schema, balance, quality)
- `test_topics_validation.py` - Topics file validation (count, domains, format)
- `test_kg_adapter_unit.py` - KG adapter with mocked KG Agent
- `test_baselines.py` - Baseline evaluators with mocked API
- `test_baselines_comprehensive.py` - Enhanced baseline tests (retry, errors)
- `test_runner.py` - Evaluation runner with mocked baselines
- `test_runner_comprehensive.py` - Enhanced runner tests (dry-run, progress)
- `test_metrics.py` - Metrics computation
- `test_eval_models.py` - Data model validation

### Integration Tests (30% of total)
- `../integration/test_kg_adapter_integration.py` - KG adapter with real pack DB
- `../integration/test_api_baselines.py` - Baselines with real API (to be created)
- `../integration/test_pack_build.py` - Pack building with 10 articles (to be created)

### E2E Tests (10% of total)
- `test_integration.py` - Complete evaluation workflow (existing)
- `../e2e/test_full_evaluation.py` - End-to-end with 5 questions (to be created)
- `../e2e/test_pack_lifecycle.py` - Build → Validate → Install → Use (to be created)

### Pack Validation
- `../test_pack_validation_physics.py` - Physics pack validation (manifest, DB, size)

## Running Tests

### All Eval Tests
```bash
pytest tests/packs/eval/ -v
```

### Unit Tests Only
```bash
pytest tests/packs/eval/ -m "not integration and not slow" -v
```

### Integration Tests (with gates)
```bash
export WIKIGR_RUN_INTEGRATION_TESTS=1
export ANTHROPIC_API_KEY="your-key"
pytest tests/integration/ -v
```

### Single Test File
```bash
pytest tests/packs/eval/test_question_schema.py -v
```

### With Coverage
```bash
pytest tests/packs/eval/ --cov=wikigr.packs.eval --cov-report=html
```

## Expected Test Status

### ✅ Currently Passing
- `test_baselines.py` - Basic baseline tests
- `test_runner.py` - Basic runner tests
- `test_metrics.py` - Metrics calculation
- `test_eval_models.py` - Data models
- `test_integration.py` - Basic integration

### ❌ Currently Failing (Expected - TDD)
- `test_question_schema.py` - Needs questions.jsonl
- `test_topics_validation.py` - Needs topics.txt
- `test_kg_adapter_unit.py` - Needs KGAdapter implementation
- `test_baselines_comprehensive.py` - Needs enhanced error handling
- `test_runner_comprehensive.py` - Needs dry-run and progress tracking

### ⏭️ Skipped (Environment Gated)
- `test_kg_adapter_integration.py` - Requires test pack
- Future API integration tests - Require ANTHROPIC_API_KEY

## What Tests Validate

### Question Set Quality
- Exactly 75 questions
- 4 domains (classical mechanics, quantum mechanics, thermodynamics, relativity)
- Domain balance: ~25% each (±5%)
- 3 difficulty levels (30% easy, 50% medium, 20% hard)
- No duplicates
- Quality reference answers (>20 chars, factual)

### Topics File Quality
- 200-500 Wikipedia article titles
- No duplicates (case-insensitive)
- Domain coverage (all 4 domains, >10% each)
- Wikipedia title format (no meta pages, no redirects)
- Foundational physics concepts included

### KG Adapter
- Context retrieval from pack DB
- Markdown formatting
- Error handling (missing DB, corrupted DB, timeouts)
- Caching behavior
- Multi-hop reasoning via graph traversal

### Baselines
- Token usage tracking
- Retry logic for API failures
- Rate limit handling
- Network error recovery
- Malformed response handling
- Batch evaluation

### Runner
- Complete evaluation workflow
- Dry-run mode (no API calls)
- Progress tracking (monotonic updates)
- Results JSON schema
- Comparative metrics
- Partial failure handling

### Pack Validation
- Manifest schema
- Database integrity (Kuzu format)
- Entity/relationship counts (5,247 articles, 14,382 entities, 23,198 relationships)
- Pack size (1.2 GB uncompressed, 340 MB compressed)
- Tarball creation/extraction
- Domain coverage

## Coverage Target

**Goal**: 80%+ coverage for new evaluation code

**Current**: ~70% (existing tests)
**After full implementation**: 82%

## Next Steps

1. ✅ Write comprehensive failing tests (COMPLETE)
2. ⏭️ Implement KG adapter (`wikigr/packs/eval/kg_adapter.py`)
3. ⏭️ Generate question set (75 questions)
4. ⏭️ Create topics file (200-500 titles)
5. ⏭️ Build test pack (10 articles)
6. ⏭️ Enhance baselines (retry, error handling)
7. ⏭️ Enhance runner (dry-run, progress)
8. ⏭️ Build full pack (5,247 articles)
9. ⏭️ Run evaluation (validate pack surpasses baselines)

See [TEST_SUMMARY.md](./TEST_SUMMARY.md) for complete test documentation.
