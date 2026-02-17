import pika
import json
import os
import sys
from datetime import datetime
from flask import Flask, jsonify

# Add common directory to path
sys.path.append('/app/common')
try:
    from ids import generate_event_id
except ImportError:
    # Fallback if common not mounted
    import uuid
    def generate_event_id():
        return str(uuid.uuid4())

app = Flask(__name__)

# In-memory inventory store
inventory_db = {
    'item_1': {'name': 'Burger', 'stock': 100, 'price': 10.0},
    'item_2': {'name': 'Pizza', 'stock': 50, 'price': 15.0},
    'item_3': {'name': 'Salad', 'stock': 75, 'price': 8.0},
}

# Track processed orders for idempotency
processed_orders = set()

# RabbitMQ connection
rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
rabbitmq_port = int(os.getenv('RABBITMQ_PORT', 5672))
rabbitmq_user = os.getenv('RABBITMQ_USER', 'admin')
rabbitmq_pass = os.getenv('RABBITMQ_PASS', 'admin123')

def get_rabbitmq_connection():
    """Create RabbitMQ connection"""
    credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
    parameters = pika.ConnectionParameters(
        host=rabbitmq_host,
        port=rabbitmq_port,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300
    )
    return pika.BlockingConnection(parameters)

def publish_inventory_event(event_type, order_id, items, reason=None):
    """Publish inventory event (reserved or failed)"""
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.exchange_declare(exchange='inventory_events', exchange_type='topic', durable=True)
        
        event = {
            'event_id': generate_event_id(),
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            'order_id': order_id,
            'items': items,
            'reason': reason
        }
        
        routing_key = 'inventory.reserved' if event_type == 'InventoryReserved' else 'inventory.failed'
        
        channel.basic_publish(
            exchange='inventory_events',
            routing_key=routing_key,
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2,
                message_id=event['event_id'],
                correlation_id=order_id
            )
        )
        
        print(f"[InventoryService] Published {event_type} event: {order_id}")
        connection.close()
        return True
    except Exception as e:
        print(f"[InventoryService] Error publishing event: {e}")
        return False

def reserve_inventory(order_id, items):
    """Reserve inventory for order items"""
    reserved_items = []
    
    for item in items:
        item_id = item.get('item_id')
        quantity = item.get('quantity', 0)
        
        if item_id not in inventory_db:
            return False, f"Item {item_id} not found", reserved_items
        
        if inventory_db[item_id]['stock'] < quantity:
            return False, f"Insufficient stock for {item_id}", reserved_items
        
        # Reserve inventory
        inventory_db[item_id]['stock'] -= quantity
        reserved_items.append({
            'item_id': item_id,
            'quantity': quantity,
            'name': inventory_db[item_id]['name']
        })
    
    return True, None, reserved_items

def process_order_placed(channel, method, properties, body):
    """Process OrderPlaced event"""
    try:
        event = json.loads(body)
        order_id = event.get('order_id')
        items = event.get('items', [])
        
        print(f"[InventoryService] Received OrderPlaced event: {order_id}", flush=True)
        
        # Idempotency check: Skip if already processed
        if order_id in processed_orders:
            print(f"[InventoryService] Order {order_id} already processed (idempotency check)")
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return
        
        # Validate message format
        if not order_id or not items:
            print(f"[InventoryService] Invalid message format: {event}")
            # Send to DLQ by rejecting without requeue
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        # Reserve inventory
        success, error_msg, reserved_items = reserve_inventory(order_id, items)
        
        if success:
            # Mark as processed
            processed_orders.add(order_id)
            
            # Publish InventoryReserved event
            publish_inventory_event('InventoryReserved', order_id, reserved_items)
            
            # Acknowledge message
            channel.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[InventoryService] Successfully reserved inventory for order {order_id}", flush=True)
        else:
            # Publish InventoryFailed event
            publish_inventory_event('InventoryFailed', order_id, items, reason=error_msg)
            
            # Acknowledge message (we processed it, even if failed)
            channel.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[InventoryService] Failed to reserve inventory for order {order_id}: {error_msg}")
            
    except json.JSONDecodeError:
        print(f"[InventoryService] Invalid JSON in message: {body}")
        # Send malformed message to DLQ
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        print(f"[InventoryService] Error processing message: {e}")
        # Reject and requeue for transient errors
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def _log(msg):
    """Print and flush so logs show up immediately in docker logs"""
    print(msg, flush=True)

def start_consumer():
    """Start consuming OrderPlaced events"""
    import time
    _log("[InventoryService] Connecting to RabbitMQ...")
    
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            _log("[InventoryService] Connected. Declaring exchanges and queue...")
            
            # Ensure exchanges and queues exist (same as OrderService: order_placed has DLX to dlq)
            channel.exchange_declare(exchange='order_events', exchange_type='topic', durable=True)
            channel.exchange_declare(exchange='inventory_events', exchange_type='topic', durable=True)
            channel.exchange_declare(exchange='dlx', exchange_type='direct', durable=True)
            try:
                channel.queue_declare(
                    queue='order_placed',
                    durable=True,
                    arguments={'x-dead-letter-exchange': 'dlx', 'x-dead-letter-routing-key': 'rejected'}
                )
                _log("[InventoryService] Queue order_placed declared (with DLX).")
            except Exception as e:
                # Queue may already exist without DLX (406 PRECONDITION_FAILED). Use existing queue.
                err_str = str(e)
                reply_code = getattr(e, 'reply_code', None)
                if reply_code == 406 or '406' in err_str or 'PRECONDITION_FAILED' in err_str:
                    _log("[InventoryService] Queue exists without DLX, using existing queue.")
                    channel = connection.channel()
                    channel.queue_declare(queue='order_placed', durable=True, passive=True)
                else:
                    raise
            channel.queue_bind(exchange='order_events', queue='order_placed', routing_key='order.placed')
            
            # Configure consumer
            channel.basic_qos(prefetch_count=1)  # Process one message at a time
            channel.basic_consume(
                queue='order_placed',
                on_message_callback=process_order_placed
            )
            
            _log("[InventoryService] Waiting for OrderPlaced events...")
            channel.start_consuming()
            
        except pika.exceptions.AMQPConnectionError:
            _log("[InventoryService] Connection lost. Reconnecting in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            _log("[InventoryService] Stopping consumer...")
            if 'channel' in locals():
                channel.stop_consuming()
            if 'connection' in locals():
                connection.close()
            break
        except Exception as e:
            _log(f"[InventoryService] Error: {e}")
            time.sleep(5)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'inventory_service',
        'inventory': inventory_db,
        'processed_orders': len(processed_orders)
    })

@app.route('/inventory', methods=['GET'])
def get_inventory():
    return jsonify(inventory_db)

if __name__ == '__main__':
    import threading
    
    # Start consumer in background thread
    consumer_thread = threading.Thread(target=start_consumer, daemon=True)
    consumer_thread.start()
    
    # Start Flask app (use_reloader=False so the consumer thread keeps running in this process)
    print("[InventoryService] Starting Inventory Service on port 5002...")
    app.run(host='0.0.0.0', port=5002, debug=True, use_reloader=False)


