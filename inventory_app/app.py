from flask import render_template, redirect, url_for, request
from flask_login import current_user
from shared.extensions import db


def register_inventory_blueprints(app):
    @app.context_processor
    def inject_inv_now():
        return {"now": __import__("datetime").datetime.utcnow()}

    @app.context_processor
    def inject_inv_settings():
        from shared.models.inventory_settings import InventorySettings
        s = InventorySettings.get()
        return {
            "purchase_flow": s.purchase_flow if s else "with_po",
            "sales_flow": s.sales_flow if s else "with_so",
        }
    from .routes.auth import inv_auth_bp
    from .routes.categories import inv_cat_bp
    from .routes.products import inv_prod_bp
    from .routes.suppliers import inv_sup_bp
    from .routes.customers import inv_cust_bp
    from .routes.purchases import inv_pur_bp
    from .routes.sales import inv_sale_bp
    from .routes.stock import inv_stock_bp
    from .routes.invoices import inv_inv_bp
    from .routes.purchase_invoice import inv_pinv_bp
    from .routes.purchase_return import inv_preturn_bp
    from .routes.vouchers import inv_vouchers_bp
    from .routes.reports import inv_reports_bp
    from .routes.settings import inv_settings_bp

    app.register_blueprint(inv_auth_bp)
    app.register_blueprint(inv_cat_bp)
    app.register_blueprint(inv_prod_bp)
    app.register_blueprint(inv_sup_bp)
    app.register_blueprint(inv_cust_bp)
    app.register_blueprint(inv_pur_bp)
    app.register_blueprint(inv_sale_bp)
    app.register_blueprint(inv_stock_bp)
    app.register_blueprint(inv_inv_bp)
    app.register_blueprint(inv_pinv_bp)
    app.register_blueprint(inv_preturn_bp)
    app.register_blueprint(inv_vouchers_bp)
    app.register_blueprint(inv_reports_bp)
    app.register_blueprint(inv_settings_bp)

    return app
