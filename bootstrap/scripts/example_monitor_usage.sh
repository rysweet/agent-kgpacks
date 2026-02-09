#!/bin/bash
# Example usage of monitor_expansion.py
# Shows how to monitor an active expansion process

echo "WikiGR Monitor Examples"
echo "======================="
echo ""

# Example 1: Basic monitoring without target
echo "Example 1: Basic monitoring (no target)"
echo "Command: python bootstrap/scripts/monitor_expansion.py --db data/wikigr.db"
echo ""
echo "Shows real-time stats without progress tracking."
echo "Useful for observing expansion without a specific goal."
echo ""

# Example 2: Monitoring with target count
echo "Example 2: Monitoring with target (1000 articles)"
echo "Command: python bootstrap/scripts/monitor_expansion.py --db data/wikigr.db --target 1000"
echo ""
echo "Shows progress bar and ETA to reach 1000 articles."
echo "Best for tracking expansion toward a specific goal."
echo ""

# Example 3: Fast refresh for active development
echo "Example 3: Fast refresh (5 second intervals)"
echo "Command: python bootstrap/scripts/monitor_expansion.py --db data/wikigr.db --target 1000 --interval 5"
echo ""
echo "Updates every 5 seconds instead of default 30."
echo "Useful during active development/testing."
echo ""

# Example 4: Monitor in background with tmux/screen
echo "Example 4: Run in background with tmux"
echo "Commands:"
echo "  tmux new -s monitor"
echo "  python bootstrap/scripts/monitor_expansion.py --db data/wikigr.db --target 1000"
echo "  # Press Ctrl+B then D to detach"
echo "  tmux attach -t monitor  # to reattach"
echo ""
echo "Keeps monitor running in background while you work."
echo ""

# Example 5: Monitor existing test databases
echo "Example 5: Monitor test databases"
echo "Command: python bootstrap/scripts/monitor_expansion.py --db data/test_100_articles.db --target 100"
echo ""
echo "View stats from completed expansion runs."
echo ""

echo "To run any example, copy the command and execute it."
echo "Press Ctrl+C to exit the monitor when done."
