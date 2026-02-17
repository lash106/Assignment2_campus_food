from kafka import KafkaProducer
import json
import time
import random
from datetime import datetime

def create_producer():
    """Create Kafka producer with retry logic"""
    max_retries = 10
    for i in range(max_retries):
        try:
            producer = KafkaProducer(
                bootstrap_servers='kafka:9092',
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda v: v.encode('utf-8') if v else None,
                acks=1
            )
            print("✓ Connected to Kafka")
            return producer
        except Exception as e:
            print(f"Waiting for Kafka... ({i+1}/{max_retries})")
            time.sleep(3)
    raise Exception("Could not connect to Kafka")

def generate_order_event(order_id):
    """Generate a random order event"""
    items = [
        {"item_name": "burger", "quantity": random.randint(1, 3)},
        {"item_name": "fries", "quantity": random.randint(1, 2)},
        {"item_name": "drink", "quantity": 1}
    ]
    
    return {
        "event_type": "OrderPlaced",
        "order_id": f"ord_{order_id}",
        "user_id": f"user_{random.randint(1, 100)}",
        "items": random.sample(items, random.randint(1, 3)),
        "timestamp": datetime.now().isoformat(),
        "total_amount": round(random.uniform(10.0, 50.0), 2)
    }

def main():
    producer = create_producer()
    
    # Publish 10,000 events for testing
    num_events = 10000
    print(f"Publishing {num_events} events...")
    
    start_time = time.time()
    
    for i in range(num_events):
        event = generate_order_event(i)
        producer.send(
            topic='order-events',
            key=event['order_id'],
            value=event
        )
        
        if (i + 1) % 1000 == 0:
            print(f"Published {i + 1} events...")
    
    producer.flush()
    elapsed = time.time() - start_time
    
    print(f"✓ Published {num_events} events in {elapsed:.2f}s ({num_events/elapsed:.0f} events/sec)")
    print("Producer will keep running. Press Ctrl+C to stop.")
    
    # Keep running so container doesn't exit
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        producer.close()

if __name__ == "__main__":
    main()