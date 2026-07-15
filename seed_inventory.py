"""Seed demo data for inventory app"""
import sys, os, json, random
from datetime import date, datetime, timedelta
sys.path.insert(0, os.path.dirname(__file__))

from inventory_app.app import create_app
from inventory_app.extensions import db
from inventory_app.models import *
from inventory_app.models.user import User

app = create_app()
random.seed(42)

with app.app_context():
    db.create_all()

    admin = User.query.filter_by(email="admin@solarkon.com").first()

    # Migrate old "draft" status to "new"
    from inventory_app.models.purchase_invoice import InvPurchaseInvoice
    migrated = InvPurchaseInvoice.query.filter_by(status="unapproved").update({"status": "new"})
    if migrated:
        db.session.commit()
        print(f"  Migrated {migrated} invoices from 'draft' → 'new'")

    if InvCategory.query.count() > 0:
        print("Data already exists, skipping seed")
        sys.exit(0)

    # Categories
    cats = []
    for name in ["Electronics", "Office Supplies", "Furniture", "Raw Materials",
                  "Packaging", "Spare Parts", "Cleaning Supplies", "Safety Equipment"]:
        c = InvCategory(name=name, description=f"{name} category")
        db.session.add(c)
        cats.append(c)
    db.session.commit()
    print(f"  Categories: {len(cats)}")

    # Products
    products = [
        ("LED-001", 'LED Monitor 24"', "Electronics", 25000, 20000, 5, 15),
        ("LED-002", 'LED Monitor 27"', "Electronics", 35000, 28000, 3, 10),
        ("KBD-001", "Wireless Keyboard", "Electronics", 3500, 2500, 10, 50),
        ("MOU-001", "Wireless Mouse", "Electronics", 1800, 1200, 10, 50),
        ("LPT-001", 'Dell Laptop Latitude', "Electronics", 120000, 100000, 2, 8),
        ("PAP-A4", "A4 Paper (ream)", "Office Supplies", 500, 350, 20, 100),
        ("PNC-001", "Ballpoint Pen (box)", "Office Supplies", 250, 150, 15, 80),
        ("FLR-001", "File Folder", "Office Supplies", 120, 70, 30, 100),
        ("STK-001", "Sticky Notes (pkt)", "Office Supplies", 150, 80, 25, 60),
        ("TNR-001", "Toner Cartridge", "Office Supplies", 8500, 6500, 3, 10),
        ("DSK-001", "Office Desk 4x2", "Furniture", 45000, 35000, 2, 5),
        ("CHR-001", "Ergonomic Chair", "Furniture", 35000, 25000, 3, 8),
        ("SHE-001", "Bookshelf 3-tier", "Furniture", 18000, 12000, 4, 6),
        ("CBL-USB", "USB Cable 3m", "Electronics", 350, 200, 50, 100),
        ("HUB-001", "USB Hub 4-port", "Electronics", 2500, 1800, 8, 20),
    ]
    cat_map = {c.name: c for c in cats}
    prod_objs = []
    for sku, name, cat_name, up, cp, stock, reorder in products:
        p = InvProduct(sku=sku, name=name, category_id=cat_map[cat_name].id,
                       unit_price=up, cost_price=cp, current_stock=stock, reorder_level=reorder)
        db.session.add(p)
        prod_objs.append(p)
    db.session.commit()
    print(f"  Products: {len(prod_objs)}")

    # Suppliers
    suppliers = [
        ("TechWorld Solutions", "Ali Ahmed", "tech@world.com", "0300-1111111", "Lahore"),
        ("OfficeMart Pakistan", "Sara Khan", "sara@officemart.pk", "0300-2222222", "Karachi"),
        ("FurnitureHub", "Usman Ali", "info@furniturehub.com", "0300-3333333", "Islamabad"),
        ("Global Electronics", "John Smith", "john@globalelec.com", "0300-4444444", "Lahore"),
        ("Stationery Plus", "Fatima Noor", "fatima@stationeryplus.com", "0300-5555555", "Karachi"),
    ]
    sup_objs = []
    for name, cp, email, phone, city in suppliers:
        s = InvSupplier(name=name, contact_person=cp, email=email, phone=phone, city=city)
        db.session.add(s)
        sup_objs.append(s)
    db.session.commit()
    print(f"  Suppliers: {len(sup_objs)}")

    # Customers
    customers = [
        ("ABC Corporation", "info@abccorp.com", "0300-6666666", "Lahore", 500000),
        ("XYZ Industries", "contact@xyz.com", "0300-7777777", "Karachi", 300000),
        ("PQR Limited", "sales@pkr.com", "0300-8888888", "Islamabad", 400000),
        ("MNO Group", "info@mnogroup.com", "0300-9999999", "Lahore", 250000),
        ("DEF Trading", "def@trading.com", "0300-0000000", "Karachi", 350000),
    ]
    cust_objs = []
    for name, email, phone, city, cl in customers:
        c = InvCustomer(name=name, email=email, phone=phone, city=city, credit_limit=cl)
        db.session.add(c)
        cust_objs.append(c)
    db.session.commit()
    print(f"  Customers: {len(cust_objs)}")

    # Purchase Orders
    po1 = InvPurchaseOrder(
        po_number="PO-202607-0001", supplier_id=sup_objs[0].id,
        order_date=date(2026, 7, 1), expected_date=date(2026, 7, 15),
        status="received", notes="Initial stock order",
        created_by=admin.id, total_amount=425000
    )
    db.session.add(po1)
    db.session.flush()
    for pid, qty, price in [(1, 5, 22000), (3, 10, 2500), (4, 20, 1200), (14, 50, 200)]:
        db.session.add(InvPurchaseOrderItem(po_id=po1.id, product_id=pid,
                                             quantity=qty, unit_price=price,
                                             total_price=qty * price))
        prod = InvProduct.query.get(pid)
        if prod:
            prod.current_stock += qty
            InvStockMovement(product_id=pid, type="purchase_in", quantity=qty,
                             reference_type="purchase_order", reference_id=po1.id,
                             notes=f"Initial stock from PO {po1.po_number}",
                             created_by=admin.id)

    po2 = InvPurchaseOrder(
        po_number="PO-202607-0002", supplier_id=sup_objs[1].id,
        order_date=date(2026, 7, 5), expected_date=date(2026, 7, 20),
        status="unapproved", notes="Office supplies restock",
        created_by=admin.id, total_amount=115000
    )
    db.session.add(po2)
    db.session.flush()
    for pid, qty, price in [(6, 50, 350), (7, 30, 150), (8, 40, 70), (9, 30, 80)]:
        db.session.add(InvPurchaseOrderItem(po_id=po2.id, product_id=pid,
                                             quantity=qty, unit_price=price,
                                             total_price=qty * price))

    po3 = InvPurchaseOrder(
        po_number="PO-202607-0003", supplier_id=sup_objs[2].id,
        order_date=date(2026, 7, 8), expected_date=date(2026, 7, 25),
        status="pending", notes="Furniture order",
        created_by=admin.id, total_amount=230000
    )
    db.session.add(po3)
    db.session.flush()
    for pid, qty, price in [(11, 3, 38000), (12, 4, 28000), (13, 2, 15000)]:
        db.session.add(InvPurchaseOrderItem(po_id=po3.id, product_id=pid,
                                             quantity=qty, unit_price=price,
                                             total_price=qty * price))
    db.session.commit()
    print(f"  Purchase Orders: {InvPurchaseOrder.query.count()}")

    # Sales Orders
    so1 = InvSalesOrder(
        so_number="SO-202607-0001", customer_id=cust_objs[0].id,
        order_date=date(2026, 7, 2), status="delivered",
        notes="First customer order", created_by=admin.id, total_amount=167500
    )
    db.session.add(so1)
    db.session.flush()
    for pid, qty, price in [(1, 2, 28000), (5, 1, 110000), (14, 10, 350)]:
        db.session.add(InvSalesOrderItem(so_id=so1.id, product_id=pid,
                                          quantity=qty, unit_price=price,
                                          total_price=qty * price))
        prod = InvProduct.query.get(pid)
        if prod:
            prod.current_stock -= qty
            InvStockMovement(product_id=pid, type="sale_out", quantity=qty,
                             reference_type="sales_order", reference_id=so1.id,
                             notes=f"Sale to {cust_objs[0].name}", created_by=admin.id)

    so2 = InvSalesOrder(
        so_number="SO-202607-0002", customer_id=cust_objs[1].id,
        order_date=date(2026, 7, 10), status="unapproved",
        notes="Pending customer confirmation", created_by=admin.id, total_amount=34400
    )
    db.session.add(so2)
    db.session.flush()
    for pid, qty, price in [(3, 5, 3500), (4, 8, 1800), (9, 10, 150)]:
        db.session.add(InvSalesOrderItem(so_id=so2.id, product_id=pid,
                                          quantity=qty, unit_price=price,
                                          total_price=qty * price))
    db.session.commit()
    print(f"  Sales Orders: {InvSalesOrder.query.count()}")

    # Invoices
    inv1 = InvInvoice(
        invoice_number="INV-SO-202607-0001",
        sales_order_id=so1.id, customer_id=cust_objs[0].id,
        invoice_date=date(2026, 7, 2), due_date=date(2026, 7, 16),
        status="unpaid", total_amount=so1.total_amount, paid_amount=0
    )
    db.session.add(inv1)
    db.session.commit()
    print(f"  Invoices: {InvInvoice.query.count()}")

    # Purchase Invoices
    from inventory_app.models.purchase_invoice import InvPurchaseInvoice, InvPurchaseInvoiceItem
    if InvPurchaseInvoice.query.count() == 0:
        admin_user = admin
        pinv1 = InvPurchaseInvoice(
            invoice_number="PINV-202607-0001", voucher_number="VCH-202607-0001",
            supplier_id=supp_objs[0].id, status="approved",
            discount_mode="general", expenses_mode="general", tax_mode="general",
            subtotal=95000, total_discount=4750, total_expenses=2500,
            total_tax=9275, net_payable=102025,
            driver_name="Imran Khan", driver_contact="0300-1234567",
            vehicle_number="LES-4562", gate_pass="GP-001",
            created_by=admin_user.id, approved_by=admin_user.id,
            approved_at=datetime.utcnow(),
        )
        db.session.add(pinv1)
        db.session.flush()
        items = [
            (1, 5, 12000, 5, 0, 0, 500, 0, 0, 10, 5),
            (2, 10, 3500, 5, 0, 0, 500, 0, 0, 10, 5),
        ]
        for pid, qty, up, dp, da, comm, fr, lu, stp, whp in items:
            total_bef = qty * up
            disc = total_bef * dp / 100 if dp > 0 else da
            total_aft = total_bef - disc
            db.session.add(InvPurchaseInvoiceItem(
                invoice_id=pinv1.id, product_id=pid, description=f"Product {pid}",
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
        db.session.commit()
        print(f"  Purchase Invoices: {InvPurchaseInvoice.query.count()}")

    # Purchase Returns
    from inventory_app.models.purchase_return import InvPurchaseReturn, InvPurchaseReturnItem
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
            for orig in pinv.items.all():
                rqty = orig.quantity // 2
                if rqty <= 0:
                    continue
                ratio = rqty / orig.quantity if orig.quantity > 0 else 0
                prop_disc = (orig.discount_amount or 0) * ratio
                net_val = (rqty * orig.unit_price) - prop_disc
                db.session.add(InvPurchaseReturnItem(
                    return_id=ret.id, product_id=orig.product_id,
                    description=orig.description,
                    original_quantity=orig.quantity,
                    previously_returned_qty=0,
                    max_returnable_qty=orig.quantity - 0,
                    current_return_qty=rqty,
                    unit=orig.unit, unit_price=orig.unit_price,
                    discount_pct=orig.discount_pct,
                    discount_amount=orig.discount_amount,
                    proportional_discount=prop_disc,
                    net_return_value=net_val,
                ))
                prod = InvProduct.query.get(orig.product_id)
                if prod:
                    prod.current_stock -= rqty
            db.session.commit()
            print(f"  Purchase Returns: {InvPurchaseReturn.query.count()}")

    # Stock movements summary
    print(f"\n  Stock movements: {InvStockMovement.query.count()}")

    # Summary
    print("\n" + "=" * 50)
    print("INVENTORY SEED COMPLETE")
    print("=" * 50)
    print(f"  Categories:         {InvCategory.query.count():4d}")
    print(f"  Products:           {InvProduct.query.count():4d}")
    print(f"  Suppliers:          {InvSupplier.query.count():4d}")
    print(f"  Customers:          {InvCustomer.query.count():4d}")
    print(f"  Purchase Orders:    {InvPurchaseOrder.query.count():4d}")
    print(f"  Sales Orders:       {InvSalesOrder.query.count():4d}")
    print(f"  Invoices:           {InvInvoice.query.count():4d}")
    print(f"  Stock Movements:    {InvStockMovement.query.count():4d}")
    print("\nDemo login: admin / admin123")
