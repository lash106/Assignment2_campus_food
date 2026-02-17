from kafka import KafkaConsumer
import json
import time
from datetime import datetime

def create_consumer():
    """Create Kafka consumer for both topics"""
    max_retries = 10
    for i in range(max_retries):
        try:
            consumer = KafkaConsumer(
                'order-events',
                'inventory-events',
                bootstrap_servers='kafka:9092',
                group_id='analytics-consumer-group',
                auto_offset_reset='earliest',
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda m: m.decode('utf-8') if m else None,
                consumer_timeout_ms=1000  # Timeout after 1 second of no messages
            )
            print("✓ Analytics Consumer connected to Kafka")
            return consumer
        except Exception as e:
            print(f"Waiting for Kafka... ({i+1}/{max_retries})")
            time.sleep(3)
    raise Exception("Could not connect to Kafka")

def main():
    consumer = create_consumer()
    
    # Metrics state
    orders_count = 0
    failures_count = 0
    window_start = time.time()
    window_duration = 60  # 60 seconds
    
    print("Analytics consumer started. Computing metrics...")
    
    try:
        while True:
            # Poll with timeout so we can check window even without messages
            messages = consumer.poll(timeout_ms=1000)
            
            for topic_partition, records in messages.items():
                for message in records:
                    event = message.value
                    event_type = event.get('event_type')
                    
                    # Count orders
                    if event_type == 'OrderPlaced':
                        orders_count += 1
                    
                    # Count failures
                    if event_type == 'InventoryFailed':
                        failures_count += 1
            
            # Commit offsets
            consumer.commit()
            
            # Check if window elapsed (happens every loop iteration)
            elapsed = time.time() - window_start
            if elapsed >= window_duration:
                # Compute metrics
                orders_per_min = orders_count
                failure_rate = (failures_count / orders_count * 100) if orders_count > 0 else 0
                
                # Print and save metrics
                timestamp = datetime.now().isoformat()
                metrics = {
                    "timestamp": timestamp,
                    "orders_per_min": orders_per_min,
                    "failure_rate": round(failure_rate, 2),
                    "total_orders": orders_count,
                    "total_failures": failures_count
                }
                
                print(f"\n--- Metrics ({timestamp}) ---")
                print(f"Orders/min: {orders_per_min}")
                print(f"Failure rate: {failure_rate:.2f}%")
                print(f"Total orders: {orders_count}, Total failures: {failures_count}\n")
                
                # Save to file
                with open('/app/metrics.json', 'a') as f:
                    f.write(json.dumps(metrics) + '\n')
                
                # Reset for next window
                orders_count = 0
                failures_count = 0
                window_start = time.time()
                
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()