"""Print recent registration payments: DB finalize state vs Razorpay capture (if keys set)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.models import RegistrationPaymentTxn, User
from app.services.payments import _razorpay_api_get


def main() -> None:
    db = SessionLocal()
    try:
        txns = (
            db.query(RegistrationPaymentTxn)
            .order_by(RegistrationPaymentTxn.id.desc())
            .limit(15)
            .all()
        )
        print("id | user_id | finalized | gateway_order | gateway_payment | user payment_status")
        print("-" * 90)
        for t in txns:
            u = db.query(User).filter(User.id == t.user_id).first()
            ps = (u.payment_status if u else "?") or "?"
            print(
                f"{t.id} | {t.user_id} | {t.is_finalized} | {(t.gateway_order_id or '')[:20]} | "
                f"{(t.gateway_payment_id or '')[:20]} | {ps}"
            )
            oid = (t.gateway_order_id or "").strip()
            if oid and t.is_finalized != "1":
                try:
                    payload = _razorpay_api_get(f"/v1/orders/{oid}/payments")
                    items = payload.get("items") or []
                    captured = [p for p in items if (p.get("status") or "").lower() == "captured"]
                    print(f"    Razorpay order {oid}: {len(captured)} captured / {len(items)} total payments")
                except Exception as exc:
                    print(f"    Razorpay lookup failed: {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
