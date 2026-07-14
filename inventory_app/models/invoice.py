from datetime import datetime
from ..extensions import db


class InvInvoice(db.Model):
    __tablename__ = "inv_invoices"
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    sales_order_id = db.Column(db.Integer, db.ForeignKey("inv_sales_orders.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("inv_customers.id"), nullable=False)
    invoice_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="draft")

    discount_mode = db.Column(db.String(20), default="general")
    tax_mode = db.Column(db.String(20), default="general")

    global_discount_pct = db.Column(db.Float, default=0)
    global_discount_value = db.Column(db.Float, default=0)
    global_sales_tax_pct = db.Column(db.Float, default=0)

    subtotal = db.Column(db.Float, default=0)
    total_discount = db.Column(db.Float, default=0)
    total_tax = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, default=0)
    paid_amount = db.Column(db.Float, default=0)

    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship("User", backref="created_invoices")
    items = db.relationship("InvInvoiceItem", backref="invoice",
                            lazy="dynamic", cascade="all, delete-orphan")


class InvInvoiceItem(db.Model):
    __tablename__ = "inv_invoice_items"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("inv_invoices.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("inv_products.id"))
    description = db.Column(db.String(300))
    quantity = db.Column(db.Float, default=1)
    unit = db.Column(db.String(20), default="pcs")
    unit_price = db.Column(db.Float, default=0)

    discount_pct = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    sales_tax_pct = db.Column(db.Float, default=0)

    total_before_discount = db.Column(db.Float, default=0)
    total_after_discount = db.Column(db.Float, default=0)

    product = db.relationship("InvProduct", backref="invoice_items")
