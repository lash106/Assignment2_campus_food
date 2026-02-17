"""
Publish a malformed message to the order_placed queue so InventoryService
rejects it and it goes to the DLQ. Then check RabbitMQ UI -> Queues -> dlq.
Usage: python send_malformed_message.py
Requires: pika, and RabbitMQ running (from host: localhost:5672 or set env RABBITMQ_HOST).
"""
import pika
import os

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'admin')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'admin123')

def main():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT, credentials=credentials)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.exchange_declare(exchange='order_events', exchange_type='topic', durable=True)

    # Option 1: Invalid JSON (will be rejected on parse)
    malformed_body = b"not valid json at all"
    # Option 2: Valid JSON but missing required fields (order_id, items)
    # malformed_body = b'{"event_type":"OrderPlaced","user_id":"x"}'

    ch.basic_publish(
        exchange='order_events',
        routing_key='order.placed',
        body=malformed_body,
        properties=pika.BasicProperties(delivery_mode=2),
    )
    print("Published malformed message to order_events (routing_key=order.placed).")
    print("InventoryService will reject it and it will go to DLQ.")
    print("Check: RabbitMQ UI http://localhost:15672 -> Queues -> dlq")
    conn.close()

if __name__ == "__main__":
    main()
