import uuid
import datetime

def generate_id(prefix: str = "order") -> str:
	"""
	Generate a unique ID with a consistent format: <prefix>-YYYYMMDD-<uuid4>
	Example: order-20260218-550e8400-e29b-41d4-a716-446655440000
	"""
	date_str = datetime.datetime.utcnow().strftime("%Y%m%d")
	unique = str(uuid.uuid4())
	return f"{prefix}-{date_str}-{unique}"
