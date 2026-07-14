def register_finance_blueprints(app):
    from .routes.reports import finance_bp
    from .routes.settings import finance_settings_bp
    app.register_blueprint(finance_bp)
    app.register_blueprint(finance_settings_bp)
    return app
