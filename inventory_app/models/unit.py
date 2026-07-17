from datetime import datetime
from ..extensions import db


class InvUnit(db.Model):
    __tablename__ = "inv_units"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    abbreviation = db.Column(db.String(20), nullable=False, unique=True)
    explanation = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __str__(self):
        return self.abbreviation
