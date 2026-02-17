"""Simple latency measurement script for the synchronous REST demo.

This script sends 10 POST requests to the Order service `/order` endpoint
and prints per-request latency plus summary statistics.

Instructions to inject a 2s delay into Inventory using docker-compose:

1. Open `sync-rest/docker-compose.yml` and set the `INVENTORY_DELAY` env var for
   the `inventory_service` to a truthy value (e.g. "1"):

   services:
     inventory_service:
       build: ./inventory_service
       ports:
         - "5001:5001"
       environment:
         - INVENTORY_DELAY=1

2. Rebuild and restart the compose stack:

   ```bash
   cd sync-rest
   docker compose up --build
   ```

Effect on the Order service response time:

- The Inventory service will sleep for 2 seconds when `INVENTORY_DELAY` is set.
- The Order service calls Inventory with a 1.0s timeout. When Inventory is
  delayed 2s, the Order service's request to Inventory will time out (~1s),
  causing the Order service to return HTTP 503 quickly (around the inventory
  timeout time, ~1s) rather than waiting the full 2s.
- Therefore enabling the 2s Inventory delay will typically make the Order
  responses return with an error around ~1 second instead of succeeding.

Usage:

  python tests/test_sync.py

Make sure the services are running (Order on port 5000 by default).
"""

import os
import time
import statistics
import requests


ORDER_URL = "http://localhost:5000/order"
TRIALS = 10


def main() -> None:
  latencies = []
  statuses = []
  output_lines = []

  header_line = f"Sending {TRIALS} requests to {ORDER_URL}\n"
  print(header_line, end="")
  output_lines.append(header_line.rstrip())

  # Table header
  hdr = f"{'#':>3} | {'status':>6} | {'latency (s)':>10}"
  sep = "----+--------+------------"
  print(hdr)
  print(sep)
  output_lines.append(hdr)
  output_lines.append(sep)

  for i in range(TRIALS):
    payload = {"test_run": True, "i": i}
    t0 = time.perf_counter()
    try:
      r = requests.post(ORDER_URL, json=payload, timeout=10)
      elapsed = time.perf_counter() - t0
      latencies.append(elapsed)
      statuses.append(r.status_code)
      line = f"{i+1:3d} | {r.status_code:6d} | {elapsed:10.3f}"
      print(line)
      output_lines.append(line)
    except requests.exceptions.RequestException as exc:
      elapsed = time.perf_counter() - t0
      latencies.append(elapsed)
      statuses.append(None)
      line = f"{i+1:3d} | {'ERR':>6} | {elapsed:10.3f}"
      print(line)
      output_lines.append(line)

  mean_latency = statistics.mean(latencies) if latencies else 0.0

  summary_lines = ["", "Summary:", f"  Success: {sum(1 for s in statuses if s == 200)}/{TRIALS}", f"  Average latency: {mean_latency:.3f}s"]
  for l in summary_lines:
    print(l)
    output_lines.append(l)

  # Save to file in the repository root for submission
  out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sync_latency.txt'))
  try:
    with open(out_path, 'w') as f:
      f.write('\n'.join(output_lines) + '\n')
    print(f"\nSaved results to {out_path}")
  except OSError as exc:
    print(f"\nFailed to write results to {out_path}: {exc}")


if __name__ == "__main__":
    main()
