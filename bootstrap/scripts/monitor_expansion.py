#!/usr/bin/env python3
"""
Real-time monitoring dashboard for WikiGR expansion

Provides live tracking of expansion progress with:
- State distribution (discovered, claimed, loaded, processed, failed)
- Progress metrics (current/target, ETA)
- Depth distribution (articles at each depth level)
- Performance statistics (rate, success/failure)
- Category breakdown (top categories)

Usage:
    python bootstrap/scripts/monitor_expansion.py --db data/wikigr.db --target 1000
"""

import kuzu
import time
from datetime import datetime, timedelta
import sys
import argparse
from typing import Optional


class ExpansionMonitor:
    """Real-time expansion monitoring dashboard"""

    def __init__(self, db_path: str, target_count: Optional[int] = None):
        """
        Initialize expansion monitor

        Args:
            db_path: Path to Kuzu database
            target_count: Target article count for progress tracking
        """
        self.db_path = db_path
        self.target_count = target_count

        # Connect to database
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)

        # Tracking metrics
        self.start_time = time.time()
        self.last_count = 0
        self.last_check_time = time.time()

    def clear_screen(self):
        """Clear terminal screen using ANSI escape codes"""
        print("\033[2J\033[H", end="")

    def get_state_distribution(self) -> dict:
        """Get article count by expansion state"""
        result = self.conn.execute("""
            MATCH (a:Article)
            RETURN a.expansion_state AS state, COUNT(a) AS count
        """)

        distribution = {}
        while result.has_next():
            row = result.get_next()
            state = row[0] if row[0] else 'unknown'
            distribution[state] = int(row[1])

        return distribution

    def get_depth_distribution(self) -> dict:
        """Get loaded article count by depth"""
        result = self.conn.execute("""
            MATCH (a:Article)
            WHERE a.expansion_state IN ['loaded', 'processed']
            RETURN a.expansion_depth AS depth, COUNT(a) AS count
            ORDER BY depth ASC
        """)

        distribution = {}
        while result.has_next():
            row = result.get_next()
            depth = int(row[0]) if row[0] is not None else -1
            distribution[depth] = int(row[1])

        return distribution

    def get_category_distribution(self, limit: int = 5) -> dict:
        """Get top categories by article count"""
        result = self.conn.execute("""
            MATCH (a:Article)
            WHERE a.expansion_state IN ['loaded', 'processed']
            RETURN a.category AS category, COUNT(a) AS count
            ORDER BY count DESC
            LIMIT $limit
        """, {"limit": limit})

        categories = {}
        while result.has_next():
            row = result.get_next()
            cat = row[0] if row[0] else 'Uncategorized'
            categories[cat] = int(row[1])

        return categories

    def get_loaded_count(self) -> int:
        """Get count of loaded articles (loaded or processed state)"""
        result = self.conn.execute("""
            MATCH (a:Article)
            WHERE a.expansion_state IN ['loaded', 'processed']
            RETURN COUNT(a) AS count
        """)

        row = result.get_next()
        return int(row[0])

    def format_bar(self, percentage: float, width: int = 40) -> str:
        """Create ASCII progress bar"""
        filled = int(percentage / 100 * width)
        bar = "█" * filled + "░" * (width - filled)
        return bar

    def format_duration(self, seconds: float) -> str:
        """Format duration as human-readable string"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def display(self):
        """Display current dashboard state"""
        self.clear_screen()

        # Header
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print("=" * 80)
        print(f"WikiGR Expansion Monitor - {timestamp}")
        print("=" * 80)

        # Get metrics
        state_dist = self.get_state_distribution()
        depth_dist = self.get_depth_distribution()
        category_dist = self.get_category_distribution()

        total_articles = sum(state_dist.values())
        loaded_count = self.get_loaded_count()

        # State Distribution
        print("\n┌─ STATE DISTRIBUTION " + "─" * 57 + "┐")

        # Sort states in meaningful order
        state_order = ['discovered', 'claimed', 'loaded', 'processed', 'failed']
        for state in state_order:
            count = state_dist.get(state, 0)
            if total_articles > 0:
                pct = 100 * count / total_articles
                bar = self.format_bar(pct, width=30)
                print(f"│ {state:12} {count:6} ({pct:5.1f}%) {bar} │")
            else:
                print(f"│ {state:12} {count:6} (  0.0%)                                │")

        # Add any unexpected states
        for state, count in state_dist.items():
            if state not in state_order:
                pct = 100 * count / total_articles if total_articles > 0 else 0
                bar = self.format_bar(pct, width=30)
                print(f"│ {state:12} {count:6} ({pct:5.1f}%) {bar} │")

        print(f"│ {'TOTAL':12} {total_articles:6} " + " " * 43 + "│")
        print("└" + "─" * 78 + "┘")

        # Progress Metrics
        if self.target_count:
            print("\n┌─ PROGRESS " + "─" * 67 + "┐")

            progress_pct = min(100, 100 * loaded_count / self.target_count)
            progress_bar = self.format_bar(progress_pct, width=50)

            print(f"│ Target:   {loaded_count:6} / {self.target_count:<6} " + " " * 47 + "│")
            print(f"│ Progress: {progress_pct:5.1f}% [{progress_bar}] │")

            # Calculate ETA
            current_time = time.time()
            elapsed = current_time - self.last_check_time

            if loaded_count > self.last_count and elapsed > 0:
                rate = (loaded_count - self.last_count) / elapsed  # articles/second
                remaining = self.target_count - loaded_count

                if rate > 0:
                    eta_seconds = remaining / rate
                    eta_str = self.format_duration(eta_seconds)
                    print(f"│ ETA:      {eta_str:>10} (at current rate)" + " " * 38 + "│")
                else:
                    print(f"│ ETA:      calculating..." + " " * 49 + "│")

            print("└" + "─" * 78 + "┘")

        # Depth Distribution
        if depth_dist:
            print("\n┌─ DEPTH DISTRIBUTION (loaded articles) " + "─" * 38 + "┐")

            max_depth = max(depth_dist.keys())
            for depth in range(max_depth + 1):
                count = depth_dist.get(depth, 0)
                pct = 100 * count / loaded_count if loaded_count > 0 else 0
                bar = self.format_bar(pct, width=30)
                print(f"│ Depth {depth}: {count:6} ({pct:5.1f}%) {bar} │")

            print("└" + "─" * 78 + "┘")

        # Performance Statistics
        print("\n┌─ PERFORMANCE " + "─" * 64 + "┐")

        elapsed_total = time.time() - self.start_time
        elapsed_str = self.format_duration(elapsed_total)

        rate = loaded_count / elapsed_total if elapsed_total > 0 else 0
        rate_per_min = rate * 60

        print(f"│ Runtime:      {elapsed_str:>10}" + " " * 55 + "│")
        print(f"│ Rate:         {rate_per_min:>10.1f} articles/minute" + " " * 35 + "│")

        if state_dist:
            success_count = state_dist.get('loaded', 0) + state_dist.get('processed', 0)
            failure_count = state_dist.get('failed', 0)
            total_processed = success_count + failure_count

            if total_processed > 0:
                success_rate = 100 * success_count / total_processed
                print(f"│ Success rate: {success_rate:>10.1f}% ({success_count}/{total_processed})" + " " * 35 + "│")

        print("└" + "─" * 78 + "┘")

        # Category Distribution
        if category_dist:
            print("\n┌─ TOP CATEGORIES " + "─" * 60 + "┐")

            for category, count in category_dist.items():
                pct = 100 * count / loaded_count if loaded_count > 0 else 0
                bar = self.format_bar(pct, width=25)
                # Truncate long category names
                cat_display = category[:20] + "..." if len(category) > 20 else category
                print(f"│ {cat_display:23} {count:6} ({pct:5.1f}%) {bar} │")

            print("└" + "─" * 78 + "┘")

        # Footer
        print("\nPress Ctrl+C to exit")

        # Update tracking
        self.last_count = loaded_count
        self.last_check_time = time.time()

    def run(self, refresh_interval: int = 30):
        """
        Run monitoring dashboard with periodic refresh

        Args:
            refresh_interval: Seconds between refreshes
        """
        try:
            while True:
                self.display()
                time.sleep(refresh_interval)
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Real-time monitoring dashboard for WikiGR expansion"
    )
    parser.add_argument(
        "--db",
        default="data/wikigr.db",
        help="Path to Kuzu database (default: data/wikigr.db)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Refresh interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--target",
        type=int,
        default=None,
        help="Target article count for progress tracking (optional)"
    )

    args = parser.parse_args()

    # Validate database exists
    from pathlib import Path
    if not Path(args.db).exists():
        print(f"Error: Database not found at {args.db}")
        sys.exit(1)

    # Create and run monitor
    monitor = ExpansionMonitor(args.db, target_count=args.target)
    monitor.run(refresh_interval=args.interval)


if __name__ == "__main__":
    main()
