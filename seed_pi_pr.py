"""Seed Purchase Invoice and Purchase Return demo data"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from datetime import datetime
from inventory_app.app import create_app
from inventory_app.extensions import db
from inventory_app.models import *
from inventory_app.models.purchase_invoice import InvPurchaseInvoice, InvPurchaseInvoiceItem
from inventory_app.models.purchase_return import InvPurchaseReturn, InvPurchaseReturnItem
from inventory_app.models.supplier import InvSupplier
from inventory_app.models.product import InvProduct
from inventory_app.models.user import User

app = create_app()
with app.app_context():
    admin = User.query.filter_by(email="admin@solarkon.com").first()
    if not admin:
        print("No admin user found, run seed_inventory.py first")
        sys.exit(1)

    if InvPurchaseInvoice.query.count() == 0:
        supp = InvSupplier.query.first()
        if not supp:
            print("No suppliers found, run seed_inventory.py first")
            sys.exit(1)

        pinv1 = InvPurchaseInvoice(
            invoice_number="PINV-202607-0001", voucher_number="VCH-202607-0001",
            supplier_id=supp.id, status="approved",
            discount_mode="general", expenses_mode="general", tax_mode="general",
            subtotal=95000, total_discount=4750, total_expenses=2500,
            total_tax=9275, net_payable=102025,
            driver_name="Imran Khan", driver_contact="0300-1234567",
            vehicle_number="LES-4562", gate_pass="GP-001",
            created_by=admin.id, approved_by=admin.id,
            approved_at=datetime.utcnow(),
        )
        db.session.add(pinv1)
        db.session.flush()

        items_data = [
            (1, 5, 12000, 5, 0, 0, 500, 0, 10, 5),
            (2, 10, 3500, 5, 0, 0, 500, 0, 10, 5),
        ]
        for pid, qty, up, dp, da, comm, fr, lu, stp, whp in items_data:
            total_bef = qty * up
            disc = total_bef * dp / 100 if dp > 0 else da
            total_aft = total_bef - disc
            db.session.add(InvPurchaseInvoiceItem(
                invoice_id=pinv1.id, product_id=pid,
                description=InvProduct.query.get(pid).name if InvProduct.query.get(pid) else f"Product {pid}",
                quantity=qty, unit="pcs", unit_price=up,
                discount_pct=dp, discount_amount=disc,
                commission=comm, freight=fr, loading_unloading=lu,
                sales_tax_pct=stp, withholding_tax_pct=whp,
                total_before_discount=total_bef,
                total_after_discount=total_aft,
            ))
            prod = InvProduct.query.get(pid)
            if prod:
                prod.current_stock += qty

        pinv2 = InvPurchaseInvoice(
            invoice_number="PINV-202607-0002", voucher_number="VCH-202607-0002",
            supplier_id=supp.id, status="approved",
            discount_mode="general", expenses_mode="general", tax_mode="general",
            subtotal=45000, total_discount=2250, total_expenses=2000,
            total_tax=4475, net_payable=49225,
            created_by=admin.id, approved_by=admin.id,
            approved_at=datetime.utcnow(),
        )
        db.session.add(pinv2)
        db.session.flush()
        for pid, qty, up in [(3, 8, 2500), (4, 5, 5000)]:
            total_bef = qty * up
            db.session.add(InvPurchaseInvoiceItem(
                invoice_id=pinv2.id, product_id=pid,
                description=InvProduct.query.get(pid).name if InvProduct.query.get(pid) else f"Product {pid}",
                quantity=qty, unit="pcs", unit_price=up,
                total_before_discount=total_bef, total_after_discount=total_bef,
            ))
            prod = InvProduct.query.get(pid)
            if prod:
                prod.current_stock += qty

        db.session.commit()
        print(f"  Purchase Invoices seeded: {InvPurchaseInvoice.query.count()}")

    if InvPurchaseReturn.query.count() == 0:
        pinv = InvPurchaseInvoice.query.filter_by(status="approved").first()
        if pinv:
            ret = InvPurchaseReturn(
                return_number="DN-202607-0001",
                original_invoice_id=pinv.id, supplier_id=pinv.supplier_id,
                status="approved", reverse_expenses=True,
                gross_return_value=25000, total_discount=1250,
                total_expenses=500, total_tax=2437.50,
                net_return_amount=26687.50,
                notes="Partial return of damaged items",
                created_by=admin.id, approved_by=admin.id,
                approved_at=datetime.utcnow(),
            )
            db.session.add(ret)
            db.session.flush()
            for orig_item in pinv.items.all():
                rqty = orig_item.quantity // 2
                if rqty <= 0:
                    continue
                ratio = rqty / orig_item.quantity if orig_item.quantity > 0 else 0
                prop_disc = (orig_item.discount_amount or 0) * ratio
                net_val = (rqty * orig_item.unit_price) - prop_disc
                db.session.add(InvPurchaseReturnItem(
                    return_id=ret.id, product_id=orig_item.product_id,
                    description=orig_item.description,
                    original_quantity=orig_item.quantity,
                    previously_returned_qty=0,
                    max_returnable_qty=orig_item.quantity,
                    current_return_qty=rqty,
                    unit=orig_item.unit, unit_price=orig_item.unit_price,
                    discount_pct=orig_item.discount_pct,
                    discount_amount=orig_item.discount_amount,
                    proportional_discount=prop_disc,
                    net_return_value=net_val,
                ))
                prod = InvProduct.query.get(orig_item.product_id)
                if prod:
                    prod.current_stock -= rqty
            db.session.commit()
            print(f"  Purchase Returns seeded: {InvPurchaseReturn.query.count()}")
        else:
            print("  No approved PI found, skipping return seed")

    print("Done")
