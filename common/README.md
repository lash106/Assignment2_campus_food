# Communication Models Lab

This repository demonstrates three inter-service communication models using Python microservices:

- **Synchronous (REST)**
- **Asynchronous (RabbitMQ)**
- **Streaming (Kafka)**

Each model implements an Order workflow with Inventory and Notification services, and includes test scenarios for latency, failure, idempotency, and replay.

---

## Project Structure

- `sync-rest/` — Synchronous REST-based services
- `async-rabbitmq/` — Asynchronous messaging with RabbitMQ
- `streaming-kafka/` — Streaming/event-driven with Kafka
- `common/` — Shared code and documentation

---

## Part A: Synchronous (REST)

- **Services:**
  - `order_service` — Exposes `POST /order`
  - `inventory_service` — Exposes `POST /reserve`
  - `notification_service` — Exposes `POST /send`
- **How it works:**
  1.  Client calls `POST /order` on OrderService
  2.  OrderService synchronously calls Inventory (`/reserve`)
  3.  If Inventory succeeds, OrderService calls Notification (`/send`)
- **Testing:**
  - Baseline latency: Run N requests, measure response times
  - Inject 2s delay in Inventory, observe order latency impact
  - Simulate Inventory failure, verify OrderService timeout/error handling
- **Results:**
  - See `sync-rest/tests/results/` for latency tables and explanations

---

## Part B: Asynchronous (RabbitMQ)

- **Services:**
  - `order_service` — Publishes `OrderPlaced` events
  - `inventory_service` — Consumes `OrderPlaced`, reserves, publishes `InventoryReserved`/`InventoryFailed`
  - `notification_service` — Consumes `InventoryReserved`, sends confirmation
- **How it works:**
  1.  OrderService writes order to local store, publishes event
  2.  InventoryService consumes, reserves, emits result event
  3.  NotificationService consumes result, sends notification
- **Testing:**
  - Kill InventoryService for 60s, keep publishing orders, restart and observe backlog drain
  - Demonstrate idempotency: re-deliver same `OrderPlaced` twice, ensure no double reserve
  - Show DLQ/poison message handling for malformed events
- **Results:**
  - See logs/screenshots in `async-rabbitmq/tests/`
  - Idempotency: See code comments in `inventory_service/consumer.py`

---

## Part C: Streaming (Kafka)

- **Services:**
  - `producer_order` — Publishes `OrderPlaced` events
  - `inventory_consumer` — Consumes orders, emits `InventoryEvents`
  - `analytics_consumer` — Consumes streams, computes metrics
- **How it works:**
  1.  Producer publishes order events
  2.  Inventory processes, emits results
  3.  Analytics computes orders/min, failure rate
- **Testing:**
  - Produce 10k events, observe consumer lag under throttling
  - Demonstrate replay: reset consumer offset, recompute metrics
- **Results:**
  - Metrics output in `streaming-kafka/analytics_consumer/metrics.json`
  - Replay evidence: see before/after metrics in logs

---

## Running the Projects

Each subfolder contains a `docker-compose.yml` for local orchestration. Example:

```sh
cd sync-rest
# or async-rabbitmq, streaming-kafka
docker-compose up --build
```

See each subfolder's `README.md` for detailed instructions, environment variables, and endpoints.

---

## Testing & Results

- Test scripts are in each project's `tests/` folder
- Results, logs, and screenshots are provided for each scenario
- See `sync-rest/tests/results/`, `async-rabbitmq/tests/`, and `streaming-kafka/test-results-screenshot/`

---

## Authors

- [Your Name Here]

---

## References

- [Flask](https://flask.palletsprojects.com/)
- [RabbitMQ](https://www.rabbitmq.com/)
- [Kafka](https://kafka.apache.org/)
