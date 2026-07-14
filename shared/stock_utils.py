from decimal import Decimal
from shared.extensions import db
from shared.models.stock_ledger import StockLedger, VoucherNumber
from shared.models.inventory_settings import InventorySettings


def dependency_check(product_id, exclude_voucher_type=None, exclude_voucher_id=None):
    q = StockLedger.query.filter(
        StockLedger.product_id == product_id,
        StockLedger.transaction_type == "OUT"
    )
    if exclude_voucher_type and exclude_voucher_id:
        q = q.filter(~(
            StockLedger.voucher_type == exclude_voucher_type,
            StockLedger.voucher_id == exclude_voucher_id
        ))
    out_qty = db.session.query(db.func.coalesce(
        db.func.sum(StockLedger.quantity), Decimal("0.0000")
    )).filter(
        StockLedger.product_id == product_id,
        StockLedger.transaction_type == "OUT"
    )
    if exclude_voucher_type and exclude_voucher_id:
        out_qty = out_qty.filter(~(
            StockLedger.voucher_type == exclude_voucher_type,
            StockLedger.voucher_id == exclude_voucher_id
        ))
    return float(out_qty.scalar() or 0)


def get_product_total_in_qty(product_id, exclude_voucher_type=None, exclude_voucher_id=None):
    q = db.session.query(db.func.coalesce(
        db.func.sum(StockLedger.quantity), Decimal("0.0000")
    )).filter(
        StockLedger.product_id == product_id,
        StockLedger.transaction_type == "IN"
    )
    if exclude_voucher_type and exclude_voucher_id:
        q = q.filter(~(
            StockLedger.voucher_type == exclude_voucher_type,
            StockLedger.voucher_id == exclude_voucher_id
        ))
    return float(q.scalar() or 0)


def validate_no_dependents(voucher_type, voucher_id, items):
    for item in items:
        pid = item.get("product_id") or (item.product_id if hasattr(item, "product_id") else item.get("id"))
        qty = float(item.get("quantity") or (item.quantity if hasattr(item, "quantity") else 0))
        out = dependency_check(pid, voucher_type, voucher_id)
        if out > 0:
            return False, pid, out
    return True, None, 0


def get_voucher_number(prefix):
    return VoucherNumber.next(prefix)


def weighted_average_unit_cost(product_id):
    _rq, rcost, ravg = StockLedger.get_running_balance(product_id)
    return ravg


def fifo_allocate(product_id, qty_to_remove):
    layers = StockLedger.query.filter_by(
        product_id=product_id, transaction_type="IN"
    ).order_by(StockLedger.id.asc()).all()
    allocated = []
    remaining = Decimal(str(qty_to_remove))
    for layer in layers:
        available = layer.running_qty
        if available <= Decimal("0.0000"):
            continue
        taken = min(available, remaining)
        allocated.append((layer, taken))
        remaining -= taken
        if remaining <= Decimal("0.0000"):
            break
    return allocated


def record_stock_movement(product_id, voucher_type, voucher_id, voucher_number,
                          transaction_type, quantity, unit_cost, notes="",
                          created_by=1):
    settings = InventorySettings.get()
    dec = settings.decimal_places
    qty = Decimal(str(quantity)).quantize(Decimal("0." + "0" * dec))
    cost = Decimal(str(unit_cost)).quantize(Decimal("0." + "0" * dec))
    total = qty * cost
    prev_qty, prev_cost, prev_avg = StockLedger.get_running_balance(product_id)
    prev_qty = Decimal(str(prev_qty))
    prev_cost = Decimal(str(prev_cost))
    prev_avg = Decimal(str(prev_avg))

    if transaction_type == "IN":
        new_total = prev_cost + total
        new_qty = prev_qty + qty
        new_avg = (new_total / new_qty).quantize(Decimal("0." + "0" * dec)) if new_qty > 0 else Decimal("0.0000")
    else:
        if settings.is_fifo():
            allocated = fifo_allocate(product_id, qty)
            removal_cost = sum(a[1] * a[0].unit_cost for a in allocated)
            new_qty = prev_qty - qty
            new_total = prev_cost - Decimal(str(removal_cost))
            new_avg = (new_total / new_qty).quantize(Decimal("0." + "0" * dec)) if new_qty > 0 else Decimal("0.0000")
        else:
            removal_cost = qty * prev_avg
            new_qty = prev_qty - qty
            new_total = prev_cost - removal_cost
            new_avg = prev_avg if new_qty > 0 else Decimal("0.0000")

    sl = StockLedger(
        product_id=product_id,
        voucher_type=voucher_type,
        voucher_id=voucher_id,
        voucher_number=voucher_number,
        transaction_type=transaction_type,
        quantity=qty,
        unit_cost=cost,
        total_cost=total,
        running_qty=new_qty,
        running_cost=new_total,
        running_avg=new_avg,
        notes=notes,
        created_by=created_by
    )
    db.session.add(sl)
    return sl


def reverse_stock_movements(voucher_type, voucher_id):
    movements = StockLedger.query.filter_by(
        voucher_type=voucher_type, voucher_id=voucher_id
    ).order_by(StockLedger.id.desc()).all()

    for m in movements:
        reverse_type = "OUT" if m.transaction_type == "IN" else "IN"
        sl = StockLedger(
            product_id=m.product_id,
            voucher_type=voucher_type,
            voucher_id=voucher_id,
            voucher_number=m.voucher_number + "-REV",
            transaction_type=reverse_type,
            quantity=m.quantity,
            unit_cost=m.unit_cost,
            total_cost=m.total_cost,
            running_qty=Decimal("0.0000"),
            running_cost=Decimal("0.0000"),
            running_avg=Decimal("0.0000"),
            notes=f"Reversal of {voucher_type} #{voucher_id}",
            created_by=m.created_by
        )
        db.session.add(sl)

    StockLedger.query.filter_by(
        voucher_type=voucher_type, voucher_id=voucher_id
    ).delete()
    db.session.flush()

    for m in movements:
        prev_qty, prev_cost, prev_avg = StockLedger.get_running_balance(m.product_id)
        if prev_qty <= 0:
            continue
        sign = -1 if reverse_type == "OUT" else 1
        new_qty = prev_qty + (sign * m.quantity)
        settings = InventorySettings.get()
        if settings.is_fifo() and reverse_type == "OUT":
            new_cost = prev_cost - (m.quantity * m.unit_cost)
        else:
            new_cost = prev_cost - (m.quantity * m.unit_cost)
        new_avg = (new_cost / new_qty).quantize(Decimal("0.0000")) if new_qty > 0 else Decimal("0.0000")
        last = StockLedger.query.filter_by(product_id=m.product_id).order_by(StockLedger.id.desc()).first()
        if last:
            last.running_qty = new_qty
            last.running_cost = new_cost
            last.running_avg = new_avg
    db.session.flush()
