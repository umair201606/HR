from flask import Blueprint, render_template, request
from flask_login import login_required
from ..extensions import db
from ..models.stock_movement import InvStockMovement
from ..models.product import InvProduct

inv_stock_bp = Blueprint("inv_stock", __name__, url_prefix="/inventory/stock")


@inv_stock_bp.route("/")
@login_required
def list_stock():
    q = request.args.get("q", "")
    low_only = request.args.get("low_only") == "1"
    query = InvProduct.query
    if q:
        query = query.filter(
            InvProduct.name.ilike(f"%{q}%") | InvProduct.sku.ilike(f"%{q}%")
        )
    if low_only:
        query = query.filter(
            InvProduct.current_stock <= InvProduct.reorder_level,
            InvProduct.reorder_level > 0
        )
    products = query.order_by(InvProduct.name).all()
    return render_template("stock/list_inv.html", products=products)


@inv_stock_bp.route("/movements")
@login_required
def list_movements():
    product_id = request.args.get("product_id", type=int)
    query = InvStockMovement.query
    if product_id:
        query = query.filter_by(product_id=product_id)
    movements = query.order_by(InvStockMovement.id.desc()).limit(100).all()
    products = InvProduct.query.filter_by(is_active=True).all()
    return render_template("stock/movements_inv.html", movements=movements, products=products)
