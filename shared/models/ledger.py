from datetime import datetime
from decimal import Decimal
from shared.extensions import db


class ChartOfAccount(db.Model):
    __tablename__ = "chart_of_accounts"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("chart_of_accounts.id"), nullable=True)
    level = db.Column(db.Integer, nullable=False, default=4)
    is_fixed = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parent = db.relationship("ChartOfAccount", remote_side=[id], backref="children")

    def is_leaf(self):
        return ChartOfAccount.query.filter_by(parent_id=self.id).count() == 0

    def can_delete(self):
        return not self.is_fixed and self.is_leaf()

    def display_path(self):
        parts = []
        a = self
        while a:
            parts.append(a.name)
            a = a.parent
        return " > ".join(reversed(parts))


class JournalEntry(db.Model):
    __tablename__ = "journal_entries"
    id = db.Column(db.Integer, primary_key=True)
    voucher_type = db.Column(db.String(50), nullable=False)
    voucher_id = db.Column(db.Integer, nullable=False)
    voucher_number = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text)
    entry_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_posted = db.Column(db.Boolean, default=True)

    lines = db.relationship("JournalLine", backref="entry", lazy="dynamic",
                            cascade="all, delete-orphan")


class JournalLine(db.Model):
    __tablename__ = "journal_lines"
    id = db.Column(db.Integer, primary_key=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey("journal_entries.id"), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("chart_of_accounts.id"), nullable=False)
    debit = db.Column(db.Numeric(16, 4), default=Decimal("0.0000"))
    credit = db.Column(db.Numeric(16, 4), default=Decimal("0.0000"))
    description = db.Column(db.Text)

    account = db.relationship("ChartOfAccount")
