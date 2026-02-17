import re

from common import ids


def test_generate_order_id_format():
    oid = ids.generate_order_id()
    assert oid.startswith("ORD-")
    assert re.fullmatch(r"ORD-[0-9a-f]{32}", oid)


def test_generate_transaction_id_format():
    tid = ids.generate_transaction_id()
    assert tid.startswith("TXN-")
    assert re.fullmatch(r"TXN-[0-9a-f]{32}", tid)


def test_uniqueness():
    a = ids.generate_order_id()
    b = ids.generate_order_id()
    c = ids.generate_transaction_id()
    d = ids.generate_transaction_id()
    assert a != b
    assert c != d
