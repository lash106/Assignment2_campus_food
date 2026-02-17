"""Utility helpers for generating unique IDs for the lab.

Provides helpers to generate Order IDs and Transaction IDs using
Python's built-in ``uuid`` library.

Functions
- ``generate_order_id()`` -> str
- ``generate_transaction_id()`` -> str

IDs use a short prefix ("ORD-" / "TXN-") followed by a UUID4 hex string.
"""
from __future__ import annotations

import uuid


def generate_order_id() -> str:
    """Generate a globally-unique Order ID.

    Returns
    -------
    str
        A string like "ORD-<uuid4-hex>" (lowercase hex, no dashes).
    """
    return f"ORD-{uuid.uuid4().hex}"


def generate_transaction_id() -> str:
    """Generate a globally-unique Transaction ID.

    Returns
    -------
    str
        A string like "TXN-<uuid4-hex>" (lowercase hex, no dashes).
    """
    return f"TXN-{uuid.uuid4().hex}"


if __name__ == "__main__":
    # Quick manual smoke-test when run directly
    print("Sample Order ID:", generate_order_id())
    print("Sample Transaction ID:", generate_transaction_id())
