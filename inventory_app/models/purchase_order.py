from datetime import datetime
from ..extensions import db


class InvPurchaseOrder(db.Model):
    __tablename__ = "inv_purchase_orders"
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(50), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("inv_suppliers.id"), nullable=False)
    order_date = db.Column(db.Date, default=datetime.utcnow)
    expected_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="draft")
    total_amount = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("InvPurchaseOrderItem", backref="purchase_order",
                            lazy="dynamic", cascade="all, delete-orphan")
    creator = db.relationship("User", backref="purchase_orders")


class InvPurchaseOrderItem(db.Model):
    __tablename__ = "inv_purchase_order_items"
    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("inv_purchase_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("inv_products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0)
    total_price = db.Column(db.Float, default=0)
