def register_finance_blueprints(app):
    from .routes.reports import finance_bp
    app.register_blueprint(finance_bp)
    return app
