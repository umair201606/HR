def register_finance_blueprints(app):
    from .routes.reports import finance_bp
    from .routes.settings import finance_settings_bp
    from .routes.accounting import acct_bp
    from .routes.coa import coa_bp
    app.register_blueprint(finance_bp)
    app.register_blueprint(finance_settings_bp)
    app.register_blueprint(acct_bp)
    app.register_blueprint(coa_bp)
    return app
