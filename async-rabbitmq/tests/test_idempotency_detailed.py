"""
Detailed idempotency test that manually republishes messages
"""
import pika
import json
import time
import requests
from datetime import datetime

RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'admin'
RABBITMQ_PASS = 'admin123'

def test_duplicate_delivery():
    """Test that duplicate OrderPlaced messages don't cause double reservation"""
    
    print("=" * 60)
    print("Detailed Idempotency Test")
    print("=" * 60)
    
    # Connect to RabbitMQ
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT, credentials=credentials)
        )
        channel = connection.channel()
    except Exception as e:
        print(f"ERROR: Could not connect to RabbitMQ: {e}")
        print("Make sure RabbitMQ is running and accessible")
        return
    
    # Get initial inventory
    try:
        inventory_before = requests.get("http://localhost:5002/inventory").json()
        stock_before = inventory_before["item_3"]["stock"]
        print(f"\nInitial stock for item_3: {stock_before}")
    except Exception as e:
        print(f"ERROR: Could not get inventory: {e}")
        connection.close()
        return
    
    # Create order via API
    order_data = {
        "user_id": "test_user",
        "items": [{"item_id": "item_3", "quantity": 3, "price": 10.0}]
    }
    
    try:
        response = requests.post("http://localhost:5001/order", json=order_data)
        order_id = response.json().get("order_id")
        print(f"Created order: {order_id}")
    except Exception as e:
        print(f"ERROR: Could not create order: {e}")
        connection.close()
        return
    
    # Wait for first processing
    print("\nWaiting for first processing (3 seconds)...")
    time.sleep(3)
    
    inventory_after_first = requests.get("http://localhost:5002/inventory").json()
    stock_after_first = inventory_after_first["item_3"]["stock"]
    print(f"Stock after first processing: {stock_after_first}")
    
    # Manually republish the same event (simulating RabbitMQ redelivery)
    event = {
        'event_id': 'test-duplicate-event',
        'event_type': 'OrderPlaced',
        'timestamp': datetime.now().isoformat(),
        'order_id': order_id,  # Same order ID
        'user_id': 'test_user',
        'items': [{"item_id": "item_3", "quantity": 3, "price": 10.0}],
        'total_amount': 30.0
    }
    
    print(f"\nRepublishing same order event (simulating duplicate delivery)...")
    print(f"Order ID: {order_id}")
    
    try:
        # Ensure exchange exists
        channel.exchange_declare(exchange='order_events', exchange_type='topic', durable=True)
        
        channel.basic_publish(
            exchange='order_events',
            routing_key='order.placed',
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2,
                message_id=event['event_id'],
                correlation_id=order_id
            )
        )
        print("Duplicate event published successfully")
    except Exception as e:
        print(f"ERROR: Could not publish duplicate event: {e}")
        connection.close()
        return
    
    # Wait for second processing attempt
    print("\nWaiting for second processing attempt (3 seconds)...")
    time.sleep(3)
    
    inventory_final = requests.get("http://localhost:5002/inventory").json()
    stock_final = inventory_final["item_3"]["stock"]
    print(f"Stock after duplicate message: {stock_final}")
    
    expected_stock = stock_before - 3
    print(f"\nExpected stock: {expected_stock} (initial: {stock_before} - reserved: 3)")
    print(f"Actual stock: {stock_final}")
    
    if stock_final == expected_stock:
        print("\n" + "=" * 60)
        print("✓ IDEMPOTENCY TEST PASSED")
        print("=" * 60)
        print(f"Stock correctly reserved once (expected: {expected_stock}, got: {stock_final})")
        print("The duplicate message was correctly ignored due to idempotency check.")
    else:
        print("\n" + "=" * 60)
        print("✗ IDEMPOTENCY TEST FAILED")
        print("=" * 60)
        print(f"Stock incorrectly reserved twice (expected: {expected_stock}, got: {stock_final})")
        print("The duplicate message was NOT properly handled.")
    
    connection.close()

if __name__ == "__main__":
    test_duplicate_delivery()


