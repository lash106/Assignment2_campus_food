from kafka import KafkaConsumer, KafkaProducer
import json
import time
import random
from datetime import datetime

def create_consumer():
    """Create Kafka consumer with retry logic"""
    max_retries = 10
    for i in range(max_retries):
        try:
            consumer = KafkaConsumer(
                'order-events',
                bootstrap_servers='kafka:9092',
                group_id='inventory-consumer-group',
                auto_offset_reset='earliest',
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda m: m.decode('utf-8') if m else None
            )
            print("✓ Inventory Consumer connected to Kafka")
            return consumer
        except Exception as e:
            print(f"Waiting for Kafka... ({i+1}/{max_retries})")
            time.sleep(3)
    raise Exception("Could not connect to Kafka")

def create_producer():
    """Create producer for publishing inventory results"""
    return KafkaProducer(
        bootstrap_servers='kafka:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda v: v.encode('utf-8') if v else None,
        acks=1
    )

def check_inventory(order_event):
    """Simulate inventory check - 80% success, 20% fail"""
    # Random failure for demonstration
    if random.random() < 0.2:
        return {
            "event_type": "InventoryFailed",
            "order_id": order_event['order_id'],
            "reason": "Insufficient stock",
            "timestamp": datetime.now().isoformat()
        }
    else:
        return {
            "event_type": "InventoryReserved",
            "order_id": order_event['order_id'],
            "reserved_items": order_event['items'],
            "timestamp": datetime.now().isoformat()
        }

def main():
    consumer = create_consumer()
    producer = create_producer()
    processed_orders = set()  # For idempotency
    
    print("Inventory consumer started. Processing orders...")
    
    try:
        for message in consumer:
            order_event = message.value
            order_id = order_event['order_id']
            
            # Idempotency check
            if order_id in processed_orders:
                print(f"⚠ Skipping duplicate order: {order_id}")
                continue
            
            # Process order
            result = check_inventory(order_event)
            time.sleep(0.01) 
            
            # Publish result
            producer.send(
                topic='inventory-events',
                key=order_id,
                value=result
            )
            
            # Mark as processed
            processed_orders.add(order_id)
            
            # Manual commit after successful processing
            consumer.commit()
            
            if len(processed_orders) % 1000 == 0:
                print(f"Processed {len(processed_orders)} orders...")
                
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        consumer.close()
        producer.close()

if __name__ == "__main__":
    main()