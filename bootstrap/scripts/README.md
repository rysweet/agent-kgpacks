# WikiGR Scripts

Utility scripts for monitoring and managing WikiGR expansion.

## monitor_expansion.py

Real-time monitoring dashboard for WikiGR expansion progress.

### Features

1. **State Distribution**
   - Shows count and percentage of articles in each state (discovered, claimed, loaded, processed, failed)
   - Visual progress bars

2. **Progress Metrics**
   - Current vs target article count
   - Progress percentage with visual bar
   - Estimated time remaining (ETA)

3. **Depth Distribution**
   - Articles loaded at each expansion depth (0, 1, 2)
   - Helps track graph growth pattern

4. **Performance Statistics**
   - Total runtime
   - Processing rate (articles/minute)
   - Success/failure rate

5. **Category Distribution**
   - Top 5 categories by article count
   - Shows knowledge graph topic diversity

### Usage

```bash
# Basic usage
python bootstrap/scripts/monitor_expansion.py --db data/wikigr.db

# With target count (enables progress bar and ETA)
python bootstrap/scripts/monitor_expansion.py --db data/wikigr.db --target 1000

# Custom refresh interval (default: 30 seconds)
python bootstrap/scripts/monitor_expansion.py --db data/wikigr.db --interval 10
```

### Options

- `--db PATH`: Path to Kuzu database (default: data/wikigr.db)
- `--interval SECONDS`: Refresh interval in seconds (default: 30)
- `--target COUNT`: Target article count for progress tracking (optional)

### Example Output

```
================================================================================
WikiGR Expansion Monitor - 2026-02-09 21:19:16
================================================================================

┌─ STATE DISTRIBUTION ─────────────────────────────────────────────────────────┐
│ discovered        0 (  0.0%) ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│ claimed           0 (  0.0%) ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│ loaded           10 (100.0%) ██████████████████████████████ │
│ processed         0 (  0.0%) ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│ failed            0 (  0.0%) ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│ TOTAL            10                                            │
└──────────────────────────────────────────────────────────────────────────────┘

┌─ PROGRESS ───────────────────────────────────────────────────────────────────┐
│ Target:       10 / 50                                                    │
│ Progress:  20.0% [██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] │
│ ETA:              2.5m (at current rate)                                   │
└──────────────────────────────────────────────────────────────────────────────┘

┌─ DEPTH DISTRIBUTION (loaded articles) ──────────────────────────────────────┐
│ Depth 0:     10 (100.0%) ██████████████████████████████ │
└──────────────────────────────────────────────────────────────────────────────┘

┌─ PERFORMANCE ────────────────────────────────────────────────────────────────┐
│ Runtime:          2.5m                                                         │
│ Rate:             4.0 articles/minute                                      │
│ Success rate:   100.0% (10/10)                                         │
└──────────────────────────────────────────────────────────────────────────────┘

┌─ TOP CATEGORIES ────────────────────────────────────────────────────────────┐
│ Computer Science             3 ( 30.0%) ███████░░░░░░░░░░░░░░░░░░ │
│ Physics                      2 ( 20.0%) █████░░░░░░░░░░░░░░░░░░░░ │
│ Biology                      2 ( 20.0%) █████░░░░░░░░░░░░░░░░░░░░ │
│ Political Science            1 ( 10.0%) ██░░░░░░░░░░░░░░░░░░░░░░░ │
│ History                      1 ( 10.0%) ██░░░░░░░░░░░░░░░░░░░░░░░ │
└──────────────────────────────────────────────────────────────────────────────┘

Press Ctrl+C to exit
```

### Notes

- Screen refreshes automatically at specified interval
- Press Ctrl+C to exit
- ETA calculation starts after first refresh showing progress
- Works with any WikiGR database following the standard schema
