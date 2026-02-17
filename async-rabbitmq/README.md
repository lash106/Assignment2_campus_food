# Async Messaging with RabbitMQ

## Overview
This implementation demonstrates asynchronous messaging using RabbitMQ for a campus food ordering system. Services communicate through events rather than direct HTTP calls, providing better decoupling, resilience, and scalability.

## Architecture

```
OrderService (Publisher)
    ↓ [OrderPlaced event]
RabbitMQ Exchange: order_events
    ↓
InventoryService (Consumer)
    ↓ [InventoryReserved/Failed event]
RabbitMQ Exchange: inventory_events
    ↓
NotificationService (Consumer)
```

## Components

1. **OrderService** (Port 5001)
   - HTTP API: `POST /order` to create orders
   - Publishes `OrderPlaced` events to RabbitMQ
   - Stores orders locally in memory
   - Endpoints:
     - `POST /order` - Create new order
     - `GET /order/<order_id>` - Get order status
     - `GET /orders` - List all orders
     - `GET /health` - Health check

2. **InventoryService** (Port 5002)
   - Consumes `OrderPlaced` events from RabbitMQ
   - Reserves inventory for orders
   - Publishes `InventoryReserved` or `InventoryFailed` events
   - Implements idempotency checks to prevent double processing
   - Endpoints:
     - `GET /inventory` - View current inventory
     - `GET /health` - Health check with processed orders count

3. **NotificationService** (Port 5003)
   - Consumes `InventoryReserved` and `InventoryFailed` events
   - Sends notifications (simulated)
   - Endpoints:
     - `GET /notifications` - List sent notifications
     - `GET /health` - Health check

## Features

- **Asynchronous Processing**: Services don't block waiting for each other
- **Resilience**: Messages persist in queues if services are down
- **Idempotency**: Duplicate messages don't cause double processing
- **Dead Letter Queue**: Malformed messages go to DLQ
- **Backlog Drain**: Messages accumulate and process when service recovers
- **Auto-reconnection**: Services automatically reconnect if RabbitMQ connection is lost

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (if running tests locally)

## Running

### Start all services with Docker Compose

```bash
cd async-rabbitmq
docker-compose up -d
```

### Check service status

```bash
# View logs
docker-compose logs -f order_service
docker-compose logs -f inventory_service
docker-compose logs -f notification_service

# Check if services are running
docker-compose ps
```

### Access RabbitMQ Management UI

Open your browser and go to: http://localhost:15672

- Username: `admin`
- Password: `admin123`

From the management UI, you can:
- View queues and message counts
- Monitor consumer connections
- Check Dead Letter Queue
- Inspect messages

### Stop services

```bash
docker-compose down
```

## Testing

### Install test dependencies

```bash
pip install requests pika
```

### Run all tests

```bash
cd tests
python test_async.py
```

### Run detailed idempotency test

```bash
cd tests
python test_idempotency_detailed.py
```

## Test Scenarios

### 1. Baseline Flow
Tests normal order creation and processing flow:
- Create an order via OrderService
- Verify inventory is reserved
- Verify notification is sent

### 2. Backlog Drain Test
Demonstrates message persistence and backlog processing:
1. Stop InventoryService
2. Send multiple orders (they queue up)
3. Restart InventoryService
4. Observe messages being processed from backlog

**To run manually:**
```bash
# Stop inventory service
docker stop inventory-service

# Send orders (they will queue)
curl -X POST http://localhost:5001/order \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "items": [{"item_id": "item_1", "quantity": 1, "price": 10.0}]}'

# Restart inventory service
docker start inventory-service

# Watch logs to see backlog drain
docker logs -f inventory-service
```

### 3. Idempotency Test
Verifies that duplicate messages don't cause double reservation:
- Send an order
- Manually republish the same order event
- Verify inventory is only reserved once

**Run the detailed test:**
```bash
python tests/test_idempotency_detailed.py
```

### 4. Dead Letter Queue (DLQ) Test
Malformed messages are rejected and sent to DLQ:
- Send a malformed message to the queue
- Check RabbitMQ Management UI → Queues → `dlq`
- Verify the message appears in DLQ

## Idempotency Strategy

The InventoryService maintains a set of processed order IDs (`processed_orders`). When receiving an `OrderPlaced` event:

1. **Check if order_id exists in `processed_orders` set**
   - If yes: Skip processing, acknowledge message (idempotent)
   - If no: Continue to step 2

2. **Process order** (reserve inventory)

3. **Add order_id to `processed_orders` set**

4. **Acknowledge message**

This ensures that even if RabbitMQ redelivers a message (due to network issues, consumer crash, etc.), it won't be processed twice.

**Note**: In production, you would use a persistent store (database) instead of in-memory set to survive service restarts.

## Message Flow

1. **Order Creation**:
   ```
   Client → POST /order → OrderService
   OrderService → Publishes OrderPlaced → RabbitMQ Queue: order_placed
   OrderService → Returns 201 Created immediately
   ```

2. **Inventory Processing**:
   ```
   InventoryService → Consumes OrderPlaced → Reserves inventory
   InventoryService → Publishes InventoryReserved → RabbitMQ Queue: inventory_reserved
   ```

3. **Notification**:
   ```
   NotificationService → Consumes InventoryReserved → Sends notification
   ```

## RabbitMQ Exchanges and Queues

### Exchanges
- `order_events` (topic) - Routes order-related events
- `inventory_events` (topic) - Routes inventory-related events

### Queues
- `order_placed` - Stores OrderPlaced events
- `inventory_reserved` - Stores InventoryReserved events
- `inventory_failed` - Stores InventoryFailed events
- `dlq` - Dead Letter Queue for rejected messages

## API Examples

### Create an order

```bash
curl -X POST http://localhost:5001/order \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "items": [
      {"item_id": "item_1", "quantity": 2, "price": 10.0},
      {"item_id": "item_2", "quantity": 1, "price": 15.0}
    ]
  }'
```

### Check order status

```bash
curl http://localhost:5001/order/ORD-20240218-abc12345
```

### View inventory

```bash
curl http://localhost:5002/inventory
```

### View notifications

```bash
curl http://localhost:5003/notifications
```

## Troubleshooting

### Services won't start
- Check if RabbitMQ is healthy: `docker-compose ps`
- Check logs: `docker-compose logs rabbitmq`
- Ensure ports 5001-5003 and 5672, 15672 are not in use

### Messages not being processed
- Check RabbitMQ Management UI for queue depth
- Verify consumers are connected: `docker-compose logs inventory_service`
- Check for connection errors in logs

### Idempotency not working
- Verify `processed_orders` set is being maintained
- Check logs for "already processed" messages
- Note: Set is in-memory, so restarting service clears it

## Production Considerations

1. **Persistent Storage**: Use a database for orders and processed order IDs
2. **Message Acknowledgment**: Ensure proper acknowledgment to prevent message loss
3. **Error Handling**: Implement retry logic with exponential backoff
4. **Monitoring**: Add metrics and monitoring for queue depths and processing times
5. **Scaling**: Use consumer groups and multiple instances for horizontal scaling
6. **DLQ Processing**: Implement a process to handle messages in DLQ

## License

This is a lab assignment implementation for CMPE-273.


