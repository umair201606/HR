from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db
from ..models.user import User
from shared.models.inventory_settings import InventorySettings

inv_auth_bp = Blueprint("inv_auth", __name__, url_prefix="/inventory")


@inv_auth_bp.route("/login", methods=["GET", "POST"])
def login():
    return redirect(url_for("auth.login"))


@inv_auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@inv_auth_bp.route("/")
@inv_auth_bp.route("/dashboard")
@login_required
def dashboard():
    from ..models.product import InvProduct
    from ..models.supplier import InvSupplier
    from ..models.customer import InvCustomer
    from ..models.purchase_order import InvPurchaseOrder
    from ..models.sales_order import InvSalesOrder
    from ..models.invoice import InvInvoice
    from ..models.stock_movement import InvStockMovement
    from shared.models.stock_ledger import StockLedger
    from shared.models.vouchers import ConsumptionVoucher, ScrapVoucher, StockAdjustmentVoucher, StockTake
    from decimal import Decimal
    from sqlalchemy import func

    total_products = InvProduct.query.count()
    total_suppliers = InvSupplier.query.count()
    total_customers = InvCustomer.query.count()
    total_purchase_orders = InvPurchaseOrder.query.count()
    total_sales_orders = InvSalesOrder.query.count()
    low_stock = InvProduct.query.filter(
        InvProduct.current_stock <= InvProduct.reorder_level,
        InvProduct.reorder_level > 0
    ).count()
    pending_po = InvPurchaseOrder.query.filter(
        InvPurchaseOrder.status.in_(["draft", "pending"])
    ).count()
    pending_so = InvSalesOrder.query.filter(
        InvSalesOrder.status.in_(["draft", "confirmed"])
    ).count()
    unpaid_invoices = InvInvoice.query.filter(
        InvInvoice.status.in_(["unpaid", "partial"])
    ).count()

    # Stock valuation
    total_stock_value = 0
    for p in InvProduct.query.filter(InvProduct.is_active == True).all():
        bal = StockLedger.get_running_balance(p.id)
        qty = float(bal[0])
        avg = float(bal[2])
        total_stock_value += qty * avg
        if p.current_stock != int(qty):
            p.current_stock = int(qty)
    db.session.commit()

    # Voucher counts
    consumption_count = ConsumptionVoucher.query.filter_by(status="approved").count()
    scrap_count = ScrapVoucher.query.filter_by(status="approved").count()
    adjustment_count = StockAdjustmentVoucher.query.filter_by(status="approved").count()
    stock_take_count = StockTake.query.filter_by(status="approved").count()
    pending_vouchers = (
        ConsumptionVoucher.query.filter_by(status="draft").count() +
        ScrapVoucher.query.filter_by(status="draft").count() +
        StockAdjustmentVoucher.query.filter_by(status="draft").count()
    )

    recent_products = InvProduct.query.order_by(InvProduct.id.desc()).limit(5).all()
    recent_movements = InvStockMovement.query.order_by(
        InvStockMovement.id.desc()
    ).limit(5).all()

    return render_template(
        "dashboard/index_inv.html",
        total_products=total_products,
        total_suppliers=total_suppliers,
        total_customers=total_customers,
        total_purchase_orders=total_purchase_orders,
        total_sales_orders=total_sales_orders,
        low_stock=low_stock,
        pending_po=pending_po,
        pending_so=pending_so,
        unpaid_invoices=unpaid_invoices,
        total_stock_value=round(total_stock_value, 2),
        consumption_count=consumption_count,
        scrap_count=scrap_count,
        adjustment_count=adjustment_count,
        stock_take_count=stock_take_count,
        pending_vouchers=pending_vouchers,
        recent_products=recent_products,
        recent_movements=recent_movements,
    )
