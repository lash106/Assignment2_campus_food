"""
Send orders every 2 seconds for 60 seconds (for backlog drain test).
Run while InventoryService is stopped.
Usage: python send_orders_60s.py
"""
import requests
import time

ORDER_URL = "http://localhost:5001/order"
DURATION = 60
INTERVAL = 2

def main():
    print(f"Sending orders every {INTERVAL}s for {DURATION}s (InventoryService should be STOPPED)...")
    start = time.time()
    count = 0
    while time.time() - start < DURATION:
        try:
            r = requests.post(
                ORDER_URL,
                json={
                    "user_id": f"backlog_user_{count}",
                    "items": [{"item_id": "item_1", "quantity": 1, "price": 10.0}]
                },
                timeout=5
            )
            if r.status_code == 201:
                count += 1
                print(f"  [{count}] Order placed: {r.json().get('order_id', '')}")
            else:
                print(f"  Error: {r.status_code} {r.text}")
        except Exception as e:
            print(f"  Request failed: {e}")
        time.sleep(INTERVAL)
    print(f"\nDone. Sent {count} orders. Restart InventoryService and watch backlog drain.")

if __name__ == "__main__":
    main()
