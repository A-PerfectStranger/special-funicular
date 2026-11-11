"""Bounded isolated notification process; only synthetic allowlisted devices in staging."""

import argparse
import json
import time

from notification_worker.provider import ExpoPush
from notification_worker.worker import process_batch, status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-runtime-seconds", type=int, default=10800)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    if not 1 <= options.max_runtime_seconds <= 10800:
        raise RuntimeError("BLOCKED: bounded runtime required")
    provider = ExpoPush.configured()
    try:
        if options.check:
            print(json.dumps(status()))
            return 0
        end = time.monotonic() + options.max_runtime_seconds
        next_status = time.monotonic()
        while time.monotonic() < end:
            result = process_batch(provider)
            if result["claimed"] or result["receipts"] or options.once:
                print(json.dumps(result), flush=True)
            if options.once:
                return 2 if result["failed"] else 0
            if time.monotonic() >= next_status:
                print(json.dumps(status()), flush=True)
                next_status = time.monotonic() + 30
            if not result["claimed"]:
                time.sleep(0.5)
        return 0
    finally:
        provider.client.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print('{"notification_unavailable":true}', flush=True)
        raise SystemExit(2) from None
