"""Standalone bounded staging archive task: no web/Django credential required."""

import argparse
import json
import time

from archive_worker.storage import WormArchive
from archive_worker.worker import process_batch, status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-runtime-seconds", type=int, default=10800)
    parser.add_argument("--once", action="store_true")
    options = parser.parse_args()
    if not 1 <= options.max_runtime_seconds <= 10800:
        raise SystemExit("BLOCKED: bounded staging runtime required")
    archive = WormArchive.configured()
    end = time.monotonic() + options.max_runtime_seconds
    next_status = time.monotonic()
    while time.monotonic() < end:
        result = process_batch(archive)
        if result["claimed"]:
            print(json.dumps(result), flush=True)
        if options.once:
            return 2 if result["failed"] else 0
        if time.monotonic() >= next_status:
            print(json.dumps(status()), flush=True)
            next_status = time.monotonic() + 30
        if not result["claimed"]:
            time.sleep(0.05)
    print('{"bounded_window_completed":true}', flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print('{"archive_unavailable":true}', flush=True)
        raise SystemExit(2) from None
