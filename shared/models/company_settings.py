from datetime import datetime, date
from shared.extensions import db


class CompanyInfo(db.Model):
    __tablename__ = "company_info"
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), default="My Company")
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    country = db.Column(db.String(100), default="Pakistan")
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    website = db.Column(db.String(200))
    tax_id = db.Column(db.String(100))
    registration_number = db.Column(db.String(100))
    logo_url = db.Column(db.String(500))
    fiscal_year_start_month = db.Column(db.Integer, default=1)
    currency = db.Column(db.String(10), default="PKR")
    currency_symbol = db.Column(db.String(10), default="Rs.")
    date_format = db.Column(db.String(20), default="Y-m-d")
    timezone = db.Column(db.String(50), default="Asia/Karachi")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        c = cls.query.first()
        if not c:
            c = cls(company_name="SolarKon Energy Solutions")
            db.session.add(c)
            db.session.commit()
        return c


class AccountingPeriod(db.Model):
    __tablename__ = "accounting_periods"
    id = db.Column(db.Integer, primary_key=True)
    fiscal_year = db.Column(db.String(10), nullable=False, index=True)
    period_name = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_open = db.Column(db.Boolean, default=True)
    is_closed = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)

    @classmethod
    def seed_current_year(cls):
        today = date.today()
        year = today.year
        fy = str(year)
        existing = cls.query.filter_by(fiscal_year=fy).count()
        if existing > 0:
            return
        db.session.add(cls(
            fiscal_year=fy,
            period_name=f"FY {fy}",
            start_date=date(year, 1, 1),
            end_date=date(year, 12, 31),
            is_open=True,
        ))
        db.session.commit()
