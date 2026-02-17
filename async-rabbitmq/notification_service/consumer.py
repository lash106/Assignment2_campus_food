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

# Store sent notifications
notifications_sent = []

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

def send_notification(order_id, items, status='confirmed'):
    """Send notification (simulated)"""
    notification = {
        'order_id': order_id,
        'status': status,
        'items': items,
        'sent_at': datetime.now().isoformat(),
        'message': f"Order {order_id} has been {status}. Items: {', '.join([i.get('name', 'Unknown') for i in items])}"
    }
    
    notifications_sent.append(notification)
    print(f"[NotificationService] Sent notification for order {order_id}: {notification['message']}")
    return notification

def process_inventory_reserved(channel, method, properties, body):
    """Process InventoryReserved event"""
    try:
        event = json.loads(body)
        order_id = event.get('order_id')
        items = event.get('items', [])
        
        print(f"[NotificationService] Received InventoryReserved event: {order_id}")
        
        # Send confirmation notification
        send_notification(order_id, items, status='confirmed')
        
        # Acknowledge message
        channel.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError:
        print(f"[NotificationService] Invalid JSON in message: {body}")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        print(f"[NotificationService] Error processing message: {e}")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def process_inventory_failed(channel, method, properties, body):
    """Process InventoryFailed event"""
    try:
        event = json.loads(body)
        order_id = event.get('order_id')
        items = event.get('items', [])
        reason = event.get('reason', 'Unknown error')
        
        print(f"[NotificationService] Received InventoryFailed event: {order_id}")
        
        # Send failure notification
        send_notification(order_id, items, status='failed')
        
        # Acknowledge message
        channel.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError:
        print(f"[NotificationService] Invalid JSON in message: {body}")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        print(f"[NotificationService] Error processing message: {e}")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def start_consumer():
    """Start consuming InventoryReserved and InventoryFailed events"""
    print("[NotificationService] Connecting to RabbitMQ...")
    
    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            
            # Ensure exchanges and queues exist
            channel.exchange_declare(exchange='inventory_events', exchange_type='topic', durable=True)
            channel.queue_declare(queue='inventory_reserved', durable=True)
            channel.queue_declare(queue='inventory_failed', durable=True)
            
            # Bind queues
            channel.queue_bind(exchange='inventory_events', queue='inventory_reserved', routing_key='inventory.reserved')
            channel.queue_bind(exchange='inventory_events', queue='inventory_failed', routing_key='inventory.failed')
            
            # Configure consumers
            channel.basic_qos(prefetch_count=1)
            
            # Consume InventoryReserved events
            channel.basic_consume(
                queue='inventory_reserved',
                on_message_callback=process_inventory_reserved
            )
            
            # Consume InventoryFailed events
            channel.basic_consume(
                queue='inventory_failed',
                on_message_callback=process_inventory_failed
            )
            
            print("[NotificationService] Waiting for inventory events...")
            channel.start_consuming()
            
        except pika.exceptions.AMQPConnectionError:
            print("[NotificationService] Connection lost. Reconnecting in 5 seconds...")
            import time
            time.sleep(5)
        except KeyboardInterrupt:
            print("[NotificationService] Stopping consumer...")
            if 'channel' in locals():
                channel.stop_consuming()
            if 'connection' in locals():
                connection.close()
            break
        except Exception as e:
            print(f"[NotificationService] Error: {e}")
            import time
            time.sleep(5)

@app.route('/', methods=['GET'])
def index():
    """Redirect to notifications list so users see notifications easily"""
    return jsonify({
        'service': 'notification_service',
        'notifications_count': len(notifications_sent),
        'notifications': notifications_sent,
        'hint': 'GET /notifications for the same list'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'notification_service',
        'notifications_sent': len(notifications_sent)
    })

@app.route('/notifications', methods=['GET'])
def list_notifications():
    return jsonify(notifications_sent)

if __name__ == '__main__':
    import threading
    
    # Start consumer in background thread
    consumer_thread = threading.Thread(target=start_consumer, daemon=True)
    consumer_thread.start()
    
    # Start Flask app
    print("[NotificationService] Starting Notification Service on port 5003...")
    app.run(host='0.0.0.0', port=5003, debug=True, use_reloader=False)


