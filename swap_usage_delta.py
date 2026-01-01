#!/usr/bin/env python3
"""
swap-usage-delta: Track swap memory usage changes over time.

This script monitors swap usage by reading /proc/meminfo and logs
deltas between readings. Useful for identifying memory pressure patterns.
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

PROC_MEMINFO = "/proc/meminfo"
DEFAULT_DATA_FILE = "swap_history.json"
DEFAULT_INTERVAL = 5


def parse_meminfo():
    """Parse /proc/meminfo and return swap-related values in kB."""
    swap_info = {}
    try:
        with open(PROC_MEMINFO, "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                key = parts[0].rstrip(":")
                value = int(parts[1])
                if key == "SwapTotal":
                    swap_info["total_kb"] = value
                elif key == "SwapFree":
                    swap_info["free_kb"] = value
                elif key == "SwapCached":
                    swap_info["cached_kb"] = value
    except FileNotFoundError:
        print(f"Error: {PROC_MEMINFO} not found. Are you on Linux?", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied reading {PROC_MEMINFO}", file=sys.stderr)
        sys.exit(1)
    
    if "total_kb" not in swap_info or "free_kb" not in swap_info:
        print("Error: Could not find swap information in meminfo", file=sys.stderr)
        sys.exit(1)
    
    swap_info["used_kb"] = swap_info["total_kb"] - swap_info["free_kb"]
    return swap_info


def format_size(kb):
    """Convert kilobytes to human-readable string."""
    if kb < 1024:
        return f"{kb} kB"
    elif kb < 1024 * 1024:
        return f"{kb / 1024:.2f} MB"
    else:
        return f"{kb / (1024 * 1024):.2f} GB"


def load_history(data_file):
    """Load existing swap history from JSON file."""
    path = Path(data_file)
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_history(data_file, history):
    """Save swap history to JSON file."""
    with open(data_file, "w") as f:
        json.dump(history, f, indent=2)


def calculate_delta(current, previous):
    """Calculate the delta between current and previous readings."""
    if previous is None:
        return {
            "total_delta": 0,
            "used_delta": 0,
            "free_delta": 0,
            "cached_delta": 0,
        }
    return {
        "total_delta": current["total_kb"] - previous["total_kb"],
        "used_delta": current["used_kb"] - previous["used_kb"],
        "free_delta": current["free_kb"] - previous["free_kb"],
        "cached_delta": current.get("cached_kb", 0) - previous.get("cached_kb", 0),
    }


def display_snapshot(swap_info, delta=None):
    """Display a formatted snapshot of current swap usage."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}]")
    print(f"  Swap Total:  {format_size(swap_info['total_kb'])}")
    print(f"  Swap Used:   {format_size(swap_info['used_kb'])}")
    print(f"  Swap Free:   {format_size(swap_info['free_kb'])}")
    if "cached_kb" in swap_info:
        print(f"  Swap Cached: {format_size(swap_info['cached_kb'])}")
    
    if delta:
        print("  --- Delta from last reading ---")
        used_sign = "+" if delta["used_delta"] > 0 else ""
        free_sign = "+" if delta["free_delta"] > 0 else ""
        if delta["used_delta"] != 0:
            print(f"  Used change: {used_sign}{format_size(delta['used_delta'])}")
        if delta["free_delta"] != 0:
            print(f"  Free change: {free_sign}{format_size(delta['free_delta'])}")
        if delta["cached_delta"] != 0:
            cached_sign = "+" if delta["cached_delta"] > 0 else ""
            print(f"  Cached change: {cached_sign}{format_size(delta['cached_delta'])}")


def run_monitor(interval, data_file, max_entries):
    """Run continuous monitoring loop."""
    history = load_history(data_file)
    previous = history[-1] if history else None
    
    print(f"Monitoring swap every {interval} seconds. Press Ctrl+C to stop.")
    print(f"Data file: {data_file}")
    
    running = True
    
    def signal_handler(sig, frame):
        nonlocal running
        running = False
        print("\nStopping monitor...")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while running:
        swap_info = parse_meminfo()
        delta = calculate_delta(swap_info, previous)
        
        display_snapshot(swap_info, delta)
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "total_kb": swap_info["total_kb"],
            "used_kb": swap_info["used_kb"],
            "free_kb": swap_info["free_kb"],
            "cached_kb": swap_info.get("cached_kb", 0),
            "delta": delta,
        }
        history.append(entry)
        
        if max_entries and len(history) > max_entries:
            history = history[-max_entries:]
        
        save_history(data_file, history)
        previous = swap_info
        
        if running:
            time.sleep(interval)
    
    print(f"Final history saved to {data_file} ({len(history)} entries)")


def show_summary(data_file):
    """Show summary statistics from history file."""
    history = load_history(data_file)
    
    if not history:
        print("No history data found. Run monitor first.")
        return
    
    print(f"Swap Usage Summary from {data_file}")
    print("=" * 50)
    print(f"Total entries: {len(history)}")
    
    if len(history) >= 2:
        first = history[0]
        last = history[-1]
        first_time = datetime.fromisoformat(first["timestamp"])
        last_time = datetime.fromisoformat(last["timestamp"])
        duration = last_time - first_time
        print(f"Time span: {first_time.strftime('%Y-%m-%d %H:%M:%S')} to {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {duration}")
    
    used_values = [entry["used_kb"] for entry in history]
    min_used = min(used_values)
    max_used = max(used_values)
    avg_used = sum(used_values) / len(used_values)
    
    print(f"\nSwap Used Statistics:")
    print(f"  Minimum: {format_size(min_used)}")
    print(f"  Maximum: {format_size(max_used)}")
    print(f"  Average: {format_size(int(avg_used))}")
    print(f"  Range:   {format_size(max_used - min_used)}")
    
    if len(history) >= 2:
        total_change = last["used_kb"] - first["used_kb"]
        sign = "+" if total_change > 0 else ""
        print(f"\nNet change over period: {sign}{format_size(total_change)}")


def show_history(data_file, limit=10):
    """Show recent history entries."""
    history = load_history(data_file)
    
    if not history:
        print("No history data found. Run monitor first.")
        return
    
    entries = history[-limit:] if limit else history
    print(f"Recent swap usage history (last {len(entries)} entries):")
    print("-" * 70)
    
    for entry in entries:
        ts = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M:%S")
        used = format_size(entry["used_kb"])
        delta = entry.get("delta", {})
        used_delta = delta.get("used_delta", 0)
        if used_delta != 0:
            sign = "+" if used_delta > 0 else ""
            delta_str = f" ({sign}{format_size(used_delta)})"
        else:
            delta_str = ""
        print(f"  {ts} - Used: {used}{delta_str}")


def main():
    parser = argparse.ArgumentParser(
        description="Track swap memory usage changes over time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Monitor with default 5s interval
  %(prog)s -i 10              # Monitor with 10s interval
  %(prog)s --summary          # Show summary from history file
  %(prog)s --history -n 20    # Show last 20 history entries
        """
    )
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Monitoring interval in seconds (default: {DEFAULT_INTERVAL})"
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        default=DEFAULT_DATA_FILE,
        help=f"Data file path (default: {DEFAULT_DATA_FILE})"
    )
    parser.add_argument(
        "-n", "--max-entries",
        type=int,
        default=1000,
        help="Maximum history entries to keep (default: 1000)"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary statistics from history file"
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show recent history entries"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Take a single reading and exit"
    )
    
    args = parser.parse_args()
    
    if args.summary:
        show_summary(args.file)
    elif args.history:
        show_history(args.file, args.max_entries)
    elif args.once:
        swap_info = parse_meminfo()
        history = load_history(args.file)
        previous = history[-1] if history else None
        delta = calculate_delta(swap_info, previous)
        display_snapshot(swap_info, delta)
    else:
        run_monitor(args.interval, args.file, args.max_entries)


if __name__ == "__main__":
    main()
