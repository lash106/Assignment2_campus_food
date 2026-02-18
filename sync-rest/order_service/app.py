from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../common')))
from ids import generate_id
import logging
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Target service URLs (use Docker service names when running under compose)
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://inventory_service:5001/reserve")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://notification_service:5002/send")

# Timeouts (seconds)
INVENTORY_TIMEOUT = float(os.getenv("INVENTORY_TIMEOUT", "1.0"))
NOTIFICATION_TIMEOUT = float(os.getenv("NOTIFICATION_TIMEOUT", "2.0"))


@app.route("/order", methods=["POST"])
def create_order():

    payload = request.get_json(silent=True) or {}
    # Assign a consistent order_id if not present
    if 'order_id' not in payload:
        payload['order_id'] = generate_id("order")

    # Call Inventory first; if it times out or is unreachable return 503
    try:
        inv_resp = requests.post(INVENTORY_URL, json=payload, timeout=INVENTORY_TIMEOUT)
        inv_resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logging.exception("Inventory call failed")
        return jsonify({"error": "inventory_unavailable", "details": str(exc)}), 503

    inventory_result = inv_resp.json()

    # Call Notification service (best-effort). If it fails, include the error
    try:
        notif_resp = requests.post(NOTIFICATION_URL, json={"order": payload, "inventory": inventory_result}, timeout=NOTIFICATION_TIMEOUT)
        notif_resp.raise_for_status()
        notif_result = notif_resp.json()
    except requests.exceptions.RequestException as exc:
        logging.warning("Notification call failed: %s", exc)
        notif_result = {"error": "notification_failed", "details": str(exc)}

    return jsonify({"status": "order_processed", "inventory": inventory_result, "notification": notif_result}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
