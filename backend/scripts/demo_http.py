"""HTTP demo: exercise the running server exactly like the extension does.

Start the server first:

    cd backend && ./scripts/run.sh          # http://localhost:5000

Then:

    .venv/bin/python scripts/demo_http.py
"""

from __future__ import annotations

import json
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"

QUERIES = [
    "Find books on forensic DNA analysis",
    "Show books on cybercrime investigation",
    "What are the library opening hours?",
    "Find publications about digital evidence and cyber forensics",
]


def main() -> None:
    print(f"# target {BASE}")
    with httpx.Client(timeout=90) as client:
        try:
            health = client.get(f"{BASE}/api/health").json()
            print(f"# health: {json.dumps(health)}")
        except Exception as exc:
            print(f"# health check failed: {exc}")

        for q in QUERIES:
            print("\n" + "=" * 80)
            print(f"USER: {q}")
            t0 = time.perf_counter()
            # This is verbatim what the extension's service worker sends.
            resp = client.post(f"{BASE}/", json={"text": q})
            dt = time.perf_counter() - t0
            print(f"  HTTP {resp.status_code}  ({dt:.1f}s)")
            data = resp.json()
            print(f"  text_summary: {data.get('text_summary')}")
            for s in data.get("sources", []):
                print(f"    - {s.get('description', '')[:100]}")
                print(f"      {s.get('url')}")


if __name__ == "__main__":
    main()
