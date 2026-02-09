# Expansion Phase Plan (Week 4)

**Goal:** Scale from 100 → 1,000 articles with optimization and monitoring

**Status:** In Progress

---

## Tasks

### ✅ Completed
- Orchestrator fully functional
- 100 seeds selected (10 categories × 10)
- Test infrastructure ready

### 🔄 In Progress
- Monitoring dashboard (agent building)
- Batch optimization experiments

### ⏳ Next
- 1K expansion (launch with monitoring)
- Quality benchmarking (20 test queries)
- Performance profiling

---

## 1K Expansion Plan

**Configuration:**
- Seeds: 100 (diverse, 10 categories)
- Target: 1,000 articles
- Max depth: 2
- Batch size: 20

**Expected:**
- Duration: 60-90 minutes
- Database: ~100 MB
- Sections: ~21,000
- P95 latency: <500ms

**Monitoring:**
- Real-time dashboard (30s refresh)
- Log file: logs/1k_expansion.log
- Progress tracking

---

## After 1K: Path to 30K

**Optimizations to apply:**
1. GPU for embeddings (10x faster)
2. Parallel Wikipedia fetching (3-5x faster)
3. Caching layer (50% speedup)

**Final push:**
- Collect 3,000 seeds
- Full BFS expansion to 30K
- Estimated: 2-4 hours with optimizations

---

**Ready to launch 1K expansion on your command!**
