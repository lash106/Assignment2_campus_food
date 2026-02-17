import uuid
from datetime import datetime

def generate_order_id():
    """Generate a unique order ID"""
    return f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

def generate_event_id():
    """Generate a unique event ID"""
    return str(uuid.uuid4())


