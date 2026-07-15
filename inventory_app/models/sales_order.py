from datetime import datetime
from ..extensions import db


class InvSalesOrder(db.Model):
    __tablename__ = "inv_sales_orders"
    id = db.Column(db.Integer, primary_key=True)
    so_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("inv_customers.id"), nullable=False)
    order_date = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.String(20), default="unapproved")
    total_amount = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("InvSalesOrderItem", backref="sales_order",
                            lazy="dynamic", cascade="all, delete-orphan")
    invoices = db.relationship("InvInvoice", backref="sales_order", lazy="dynamic")
    creator = db.relationship("User", backref="sales_orders")


class InvSalesOrderItem(db.Model):
    __tablename__ = "inv_sales_order_items"
    id = db.Column(db.Integer, primary_key=True)
    so_id = db.Column(db.Integer, db.ForeignKey("inv_sales_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("inv_products.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0)
    total_price = db.Column(db.Float, default=0)
