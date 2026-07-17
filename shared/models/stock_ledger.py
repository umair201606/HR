from datetime import datetime
from decimal import Decimal
from shared.extensions import db


class StockLedger(db.Model):
    __tablename__ = "stock_ledger"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False, index=True)
    voucher_type = db.Column(db.String(50), nullable=False)
    voucher_id = db.Column(db.Integer, nullable=False)
    voucher_number = db.Column(db.String(50), nullable=False, index=True)
    transaction_type = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Numeric(16, 4), nullable=False)
    unit_cost = db.Column(db.Numeric(16, 4), nullable=False)
    total_cost = db.Column(db.Numeric(16, 4), nullable=False)
    running_qty = db.Column(db.Numeric(16, 4), nullable=False)
    running_cost = db.Column(db.Numeric(16, 4), nullable=False)
    running_avg = db.Column(db.Numeric(16, 4), nullable=False)
    # Method in force when this row was priced. Audit only — cost comes from
    # the layers, never from re-interpreting history under today's method.
    valuation_method = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    notes = db.Column(db.Text)

    @classmethod
    def get_running_balance(cls, product_id):
        last = cls.query.filter_by(product_id=product_id).order_by(cls.id.desc()).first()
        if last:
            return last.running_qty, last.running_cost, last.running_avg
        return Decimal("0.0000"), Decimal("0.0000"), Decimal("0.0000")


class VoucherNumber(db.Model):
    __tablename__ = "voucher_numbers"
    id = db.Column(db.Integer, primary_key=True)
    prefix = db.Column(db.String(20), nullable=False, unique=True)
    next_number = db.Column(db.Integer, nullable=False, default=1)

    @classmethod
    def next(cls, prefix):
        v = cls.query.filter_by(prefix=prefix).first()
        if not v:
            v = cls(prefix=prefix, next_number=1)
            db.session.add(v)
            db.session.commit()
        num = v.next_number
        v.next_number += 1
        db.session.commit()
        return f"{prefix}-{num:05d}"
