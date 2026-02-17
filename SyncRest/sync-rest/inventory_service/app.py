from __future__ import annotations

import os
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

# Toggle a 2-second artificial delay by setting INVENTORY_DELAY to
# a truthy value ("1", "true", "yes") in the environment.
INVENTORY_DELAY = os.getenv("INVENTORY_DELAY", "0").lower() in ("1", "true", "yes")


@app.route("/reserve", methods=["POST"])
def reserve():
    payload = request.get_json(silent=True) or {}
    if INVENTORY_DELAY:
        time.sleep(2)
    # In a realistic service you'd check stock and persist reservation.
    return jsonify({"status": "reserved", "request": payload}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
