from flask import Flask, request, jsonify
import pika
import json
import os
import sys
from datetime import datetime

# Add common directory to path
sys.path.append('/app/common')
try:
    from ids import generate_order_id, generate_event_id
except ImportError:
    # Fallback if common not mounted
    import uuid
    def generate_order_id():
        return f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    def generate_event_id():
        return str(uuid.uuid4())

app = Flask(__name__)

# In-memory order store
orders_db = {}

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
        credentials=credentials
    )
    return pika.BlockingConnection(parameters)

def setup_rabbitmq():
    """Setup RabbitMQ exchanges and queues"""
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    
    # Declare exchanges
    channel.exchange_declare(exchange='order_events', exchange_type='topic', durable=True)
    channel.exchange_declare(exchange='inventory_events', exchange_type='topic', durable=True)
    channel.exchange_declare(exchange='dlx', exchange_type='direct', durable=True)  # Dead-letter exchange
    
    # Declare queues (order_placed sends rejected messages to dlq)
    try:
        channel.queue_declare(
            queue='order_placed',
            durable=True,
            arguments={'x-dead-letter-exchange': 'dlx', 'x-dead-letter-routing-key': 'rejected'}
        )
    except pika.exceptions.ChannelClosedByBroker as e:
        # Queue already exists without DLX (e.g. from before we added DLQ). Use existing queue.
        if e.reply_code != 406:
            raise
        channel = connection.channel()
        channel.queue_declare(queue='order_placed', durable=True, passive=True)
    channel.queue_declare(queue='inventory_reserved', durable=True)
    channel.queue_declare(queue='inventory_failed', durable=True)
    channel.queue_declare(queue='dlq', durable=True)
    channel.queue_bind(exchange='dlx', queue='dlq', routing_key='rejected')
    
    # Bind queues to exchanges
    channel.queue_bind(exchange='order_events', queue='order_placed', routing_key='order.placed')
    channel.queue_bind(exchange='inventory_events', queue='inventory_reserved', routing_key='inventory.reserved')
    channel.queue_bind(exchange='inventory_events', queue='inventory_failed', routing_key='inventory.failed')
    
    connection.close()

def publish_order_placed(order_data):
    """Publish OrderPlaced event to RabbitMQ"""
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        # Ensure exchange exists (idempotent; handles startup race)
        channel.exchange_declare(exchange='order_events', exchange_type='topic', durable=True)
        
        event = {
            'event_id': generate_event_id(),
            'event_type': 'OrderPlaced',
            'timestamp': datetime.now().isoformat(),
            'order_id': order_data['order_id'],
            'user_id': order_data['user_id'],
            'items': order_data['items'],
            'total_amount': order_data['total_amount']
        }
        
        channel.basic_publish(
            exchange='order_events',
            routing_key='order.placed',
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                message_id=event['event_id'],
                correlation_id=order_data['order_id']
            )
        )
        
        print(f"[OrderService] Published OrderPlaced event: {order_data['order_id']}")
        connection.close()
        return True
    except Exception as e:
        print(f"[OrderService] Error publishing event: {e}")
        return False

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'order_service'})

@app.route('/order', methods=['POST'])
def create_order():
    """Create a new order and publish OrderPlaced event"""
    try:
        data = request.json
        
        # Validate input
        if not data or 'user_id' not in data or 'items' not in data:
            return jsonify({'error': 'Invalid request. user_id and items required'}), 400
        
        # Generate order ID
        order_id = generate_order_id()
        
        # Calculate total amount
        total_amount = sum(item.get('price', 0) * item.get('quantity', 0) for item in data['items'])
        
        # Create order record
        order_data = {
            'order_id': order_id,
            'user_id': data['user_id'],
            'items': data['items'],
            'total_amount': total_amount,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        
        # Store order locally
        orders_db[order_id] = order_data
        
        # Publish event to RabbitMQ
        if publish_order_placed(order_data):
            return jsonify({
                'order_id': order_id,
                'status': 'pending',
                'message': 'Order created and queued for processing'
            }), 201
        else:
            return jsonify({'error': 'Failed to publish order event'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/order/<order_id>', methods=['GET'])
def get_order(order_id):
    """Get order status"""
    if order_id in orders_db:
        return jsonify(orders_db[order_id])
    return jsonify({'error': 'Order not found'}), 404

@app.route('/orders', methods=['GET'])
def list_orders():
    """List all orders"""
    return jsonify(list(orders_db.values()))

if __name__ == '__main__':
    print("[OrderService] Setting up RabbitMQ...")
    try:
        setup_rabbitmq()
    except Exception as e:
        print(f"[OrderService] Warning: Could not setup RabbitMQ immediately: {e}")
        print("[OrderService] Will retry on first publish...")
    print("[OrderService] Starting Order Service on port 5001...")
    # use_reloader=False so consumer threads in other services don't get orphaned; same for Docker
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)


