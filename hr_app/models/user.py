from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db, login_manager


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    users = db.relationship("User", backref="role_obj", lazy="dynamic")

    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"

    @staticmethod
    def seed():
        for r in [Role.ADMIN, Role.MANAGER, Role.EMPLOYEE]:
            if not Role.query.filter_by(name=r).first():
                db.session.add(Role(name=r, description=f"{r.title()} role"))


class Permission(db.Model):
    __tablename__ = "permissions"
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    resource = db.Column(db.String(100), nullable=False)
    can_read = db.Column(db.Boolean, default=False)
    can_write = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)

    @staticmethod
    def seed():
        admin_role = Role.query.filter_by(name=Role.ADMIN).first()
        mgr_role = Role.query.filter_by(name=Role.MANAGER).first()
        emp_role = Role.query.filter_by(name=Role.EMPLOYEE).first()
        all_resources = [
            "attendance", "leaves", "ess", "reports", "mss",
            "workplace", "timesheets", "digital_files",
            "compensation", "communications", "pf", "users"
        ]
        for r in all_resources:
            if not Permission.query.filter_by(role_id=admin_role.id, resource=r).first():
                db.session.add(Permission(role_id=admin_role.id, resource=r, can_read=True, can_write=True, can_delete=True))
            if not Permission.query.filter_by(role_id=mgr_role.id, resource=r).first():
                write_resources = ["mss", "workplace", "timesheets", "leaves"]
                db.session.add(Permission(role_id=mgr_role.id, resource=r, can_read=True, can_write=r in write_resources))
            if not Permission.query.filter_by(role_id=emp_role.id, resource=r).first():
                read_resources = ["attendance", "leaves", "ess", "workplace", "digital_files", "communications", "pf"]
                db.session.add(Permission(role_id=emp_role.id, resource=r, can_read=r in read_resources, can_write=r in ["attendance", "leaves", "ess", "timesheets"]))


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    designation = db.Column(db.String(100))
    department = db.Column(db.String(100))
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    date_of_birth = db.Column(db.Date)
    date_of_joining = db.Column(db.Date, default=date.today)
    phone = db.Column(db.String(20))
    cnic = db.Column(db.String(20))
    bank_name = db.Column(db.String(100))
    bank_account_title = db.Column(db.String(100))
    bank_account_number = db.Column(db.String(50))
    emergency_contact = db.Column(db.String(100))
    emergency_phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    profile_image = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = db.relationship("User", remote_side=[id], backref="direct_reports")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, resource, action="read"):
        perm = Permission.query.filter_by(role_id=self.role_id, resource=resource).first()
        if not perm:
            return False
        if action == "read":
            return perm.can_read
        if action == "write":
            return perm.can_write
        if action == "delete":
            return perm.can_delete
        return False

    def is_admin(self):
        return self.role_obj and self.role_obj.name == Role.ADMIN

    def is_manager(self):
        return self.role_obj and self.role_obj.name == Role.MANAGER

    def is_employee(self):
        return self.role_obj and self.role_obj.name == Role.EMPLOYEE

    def get_role_name(self):
        return self.role_obj.name if self.role_obj else ""

    def __repr__(self):
        return f"<User {self.full_name}>"


class ChangeRequest(db.Model):
    __tablename__ = "change_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    field_name = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending")
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    review_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)

    user = db.relationship("User", foreign_keys=[user_id], backref="change_requests")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
