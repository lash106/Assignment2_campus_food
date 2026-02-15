# Distributed Systems Lab — Sync REST demo

This repo contains a small synchronous REST demo with three Flask services (Order, Inventory, Notification), a `docker-compose` stack, and a test script that measures latency for the `/order` endpoint under different failure/delay scenarios.

Files of interest
- `sync-rest/` — compose setup and service code
- `tests/test_sync.py` — latency tester (sends 10 POSTs to http://localhost:5000/order and saves results)
- `sync_latency_baseline.txt`, `sync_latency_delay.txt`, `sync_latency_failure.txt`, `sync_latency_summary.txt` — results produced during testing
- `requirements.txt` — Python deps for running the test script locally (`flask`, `requests`, `pytest`)

Quick start (team workflow)

1. Clone the repo (or pull latest changes):

   git clone <repo-url>
   cd <repo-folder>

2. Start the services via Docker Compose:

   cd sync-rest
   docker compose up --build -d

   - By default the compose file defines an env var `INVENTORY_DELAY` for the inventory service.
   - To run the baseline test ensure `INVENTORY_DELAY=0` in `sync-rest/docker-compose.yml` then rebuild and start.

3. Prepare a local Python virtual environment for the test runner (optional but recommended):

   cd ..   # repo root
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

4. Run the baseline latency test:

   python tests/test_sync.py

   - The script saves output to `sync_latency.txt` by default; when run here it creates files named:
     `sync_latency_baseline.txt`, `sync_latency_delay.txt`, `sync_latency_failure.txt` (depending on which test you ran).

Delay injection (Inventory sleeps 2s)

- To inject a 2s artificial delay into Inventory, set `INVENTORY_DELAY=1` in `sync-rest/docker-compose.yml`, then rebuild and restart the stack:

  cd sync-rest
  docker compose up --build -d

- Run `python ../tests/test_sync.py` from the repo root to measure the effect.

Failure simulation (Inventory down)

- To simulate Inventory failure:

  cd sync-rest
  docker compose stop inventory_service

- Then run the test script again; the Order service should return 503 quickly.

Notes on observed behavior (analysis)
- Baseline: Order calls Inventory then Notification; average latency is small when Inventory responds.
- With 2s Inventory delay: Order uses a 1s inventory timeout — requests time out (~1s) and return HTTP 503. Average latency increases to roughly the inventory timeout.
- With Inventory stopped: connection failures are detected quickly and Order returns 503 with low latency.

Deliverables for submission
- `sync_latency_baseline.txt`
- `sync_latency_delay.txt`
- `sync_latency_failure.txt`
- `sync_latency_summary.txt`

