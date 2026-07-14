from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)

    @classmethod
    def seed_current_year(cls):
        today = date.today()
        year = today.year
        fy = f"{year}-{year+1}" if today.month >= 7 else f"{year-1}-{year}"
        existing = cls.query.filter_by(fiscal_year=fy).count()
        if existing > 0:
            return
        start_m = 7
        start_y = year if today.month >= 7 else year - 1
        period_start = date(start_y, start_m, 1)
        for i in range(12):
            ps = period_start + relativedelta(months=i)
            pe = (ps + relativedelta(months=1)) - timedelta(days=1)
            month_names = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
                           "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
            db.session.add(cls(
                fiscal_year=fy,
                period_name=f"{month_names[i]} {ps.year}",
                start_date=ps,
                end_date=pe,
                is_open=True,
            ))
        db.session.commit()
