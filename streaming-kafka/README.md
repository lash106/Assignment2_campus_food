# Part C: Streaming with Kafka

## How to Run
```bash
docker-compose up -d
```

Wait 30 seconds for Kafka to start, then check logs:
```bash
docker-compose logs producer
docker-compose logs inventory-consumer
docker-compose logs analytics-consumer
```

## Services

- **Zookeeper + Kafka**: Streaming infrastructure
- **Producer**: Publishes 10,000 OrderPlaced events to `order-events` topic
- **Inventory Consumer**: Consumes orders, simulates inventory check, publishes results to `inventory-events`
- **Analytics Consumer**: Consumes both topics, computes orders/min and failure rate every 60 seconds

## Test 1: Produce 10k Events
```bash
docker-compose logs producer
```

Expected output:
```
✓ Published 10000 events in 2.56s (3914 events/sec)
```

## Test 2: Consumer Lag Under Throttling

Inventory consumer has a 10ms artificial delay per message. Monitor lag:
```bash
docker-compose exec kafka kafka-consumer-groups --bootstrap-server kafka:9092 \
  --describe --group inventory-consumer-group
```

Run repeatedly to observe LAG column decreasing from ~9662 to 0 as the throttled consumer catches up.

## Test 3: Replay

**Step 1**: Record current metrics:
```bash
docker-compose logs analytics-consumer | tail -20
```

**Step 2**: Stop analytics consumer and reset offsets to beginning:
```bash
docker-compose stop analytics-consumer
sleep 10
docker-compose exec kafka kafka-consumer-groups --bootstrap-server kafka:9092 \
  --group analytics-consumer-group --topic order-events \
  --reset-offsets --to-earliest --execute

docker-compose exec kafka kafka-consumer-groups --bootstrap-server kafka:9092 \
  --group analytics-consumer-group --topic inventory-events \
  --reset-offsets --to-earliest --execute
```

**Step 3**: Restart and check metrics:
```bash
docker-compose start analytics-consumer
sleep 90
docker-compose logs analytics-consumer | tail -20
```

### Replay Results

| Run | Orders/min | Failure Rate |
|-----|-----------|--------------|
| Before replay | 10000 | 7.08% |
| After replay | 10000 | 19.34% |

**Why failure rates differ**: The inventory check uses `random.random()` to simulate stock availability, so each replay re-simulates outcomes rather than replaying recorded results. In a production system, actual inventory decisions would be stored in the event payload, making replay fully deterministic.

## Teardown
```bash
docker-compose down -v
```