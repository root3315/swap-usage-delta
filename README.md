# swap-usage-delta

Track swap memory usage changes over time. Because sometimes you need to know *why* your system is crawling at 3pm.

## What it does

Reads `/proc/meminfo`, tracks swap usage, and logs deltas between readings. Helps you spot memory pressure patterns, identify which processes might be thrashing, or just prove to your team that yes, the system *is* leaking memory.

## Quick start

```bash
python3 swap_usage_delta.py
```

That's it. Runs every 5 seconds until you hit Ctrl+C. Data goes to `swap_history.json`.

## Other useful commands

```bash
# Custom interval (10 seconds)
python3 swap_usage_delta.py -i 10

# Just grab one reading
python3 swap_usage_delta.py --once

# See what you've collected
python3 swap_usage_delta.py --summary

# Show recent history
python3 swap_usage_delta.py --history -n 20
```

## Output format

```
[2026-03-12 14:30:05]
  Swap Total:  8.00 GB
  Swap Used:   1.23 GB
  Swap Free:   6.77 GB
  Swap Cached: 512 MB
  --- Delta from last reading ---
  Used change: +45.50 MB
  Free change: -45.50 MB
```

The delta tells you if swap is growing or shrinking since the last check. Positive used delta = bad news, probably.

## Data file

History is stored as JSON. You can parse it yourself if you want graphs or whatever:

```json
{
  "timestamp": "2026-03-12T14:30:05",
  "total_kb": 8388608,
  "used_kb": 1289748,
  "free_kb": 7098860,
  "cached_kb": 524288,
  "delta": { ... }
}
```

## Why I wrote this

Had a server that'd randomly slow to a crawl. `free -h` showed swap usage but not *when* it spiked. This script caught the pattern: every day at 2pm, some batch job would eat 2GB of swap in 5 minutes. Turned out to be an unoptimized database query. Fixed the query, problem solved.

## Requirements

- Linux (reads `/proc/meminfo`)
- Python 3.6+

No external dependencies. The `requirements.txt` is basically a formality.

## Caveats

- Needs read access to `/proc/meminfo` (usually fine for any user)
- Only tracks swap, not which processes are using it (that's a different tool)
- JSON file grows over time, but defaults to keeping last 1000 entries

## License

Do what you want with it.
