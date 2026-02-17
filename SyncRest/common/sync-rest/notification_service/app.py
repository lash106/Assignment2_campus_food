from __future__ import annotations

from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/send", methods=["POST"])
def send():
    payload = request.get_json(silent=True) or {}
    # Simulate sending notification (email/SMS/etc.)
    return jsonify({"status": "sent", "request": payload}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
