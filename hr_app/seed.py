"""Seed script to populate the database with demo data."""
from datetime import date, timedelta
from .app import create_app
from .extensions import db
from .models.user import User, Role
from .models.leave import LeaveType, LeaveQuota
from .models.compensation import PayrollProfile, PayrollComponent
from .models.pf import ProvidentFundConfig
from .models.digital_file import FileCategory

app = create_app()

with app.app_context():
    if User.query.first():
        print("Database already seeded.")
        exit()

    # Create leave types
    leave_types = [
        LeaveType(name="Casual Leave", code="CL", default_quota=12, is_paid=True, carry_forward=False),
        LeaveType(name="Sick Leave", code="SL", default_quota=10, is_paid=True, carry_forward=True, max_carry_forward=5),
        LeaveType(name="Annual Leave", code="AL", default_quota=20, is_paid=True, carry_forward=True, max_carry_forward=10),
    ]
    db.session.add_all(leave_types)

    # File categories
    cats = [
        FileCategory(name="CNIC"), FileCategory(name="Educational Certificates"),
        FileCategory(name="Employment Contract"), FileCategory(name="Bank Details"),
        FileCategory(name="Medical Reports"), FileCategory(name="Other"),
    ]
    db.session.add_all(cats)

    # PF Config
    db.session.add(ProvidentFundConfig(
        employee_contribution_pct=5.0, employer_contribution_pct=5.0,
        max_loan_percentage=50.0, min_service_months_for_loan=12
    ))

    # Users
    admin = User(employee_code="ADM001", email="admin@solarkon.com",
                 full_name="Admin User", designation="HR Director",
                 department="Human Resources", role_id=Role.query.filter_by(name=Role.ADMIN).first().id,
                 date_of_joining=date.today() - timedelta(days=365*5), phone="0300-1111111",
                 cnic="42101-1234567-1", bank_name="HBL", bank_account_title="Admin User",
                 bank_account_number="0012-3456789-01")
    admin.set_password("admin123")
    db.session.add(admin)
    db.session.flush()

    manager = User(employee_code="MGR001", email="manager@solarkon.com",
                   full_name="Manager User", designation="Department Manager",
                   department="Engineering", role_id=Role.query.filter_by(name=Role.MANAGER).first().id,
                   manager_id=admin.id, date_of_joining=date.today() - timedelta(days=365*3),
                   phone="0300-2222222", cnic="42101-7654321-2",
                   bank_name="UBL", bank_account_title="Manager User",
                   bank_account_number="0098-7654321-02")
    manager.set_password("mgr123")
    db.session.add(manager)
    db.session.flush()

    employees = []
    emp_data = [
        ("EMP001", "John Doe", "Software Engineer", "Engineering", "0300-3333333", "42101-1111111-3"),
        ("EMP002", "Jane Smith", "QA Engineer", "Engineering", "0300-4444444", "42101-2222222-4"),
        ("EMP003", "Bob Wilson", "DevOps Engineer", "Engineering", "0300-5555555", "42101-3333333-5"),
    ]
    emp_role = Role.query.filter_by(name=Role.EMPLOYEE).first()
    for code, name, desig, dept, phone, cnic in emp_data:
        u = User(employee_code=code, email=f"{name.lower().replace(' ', '.')}@solarkon.com",
                 full_name=name, designation=desig, department=dept,
                 role_id=emp_role.id, manager_id=manager.id,
                 date_of_joining=date.today() - timedelta(days=365*2),
                 phone=phone, cnic=cnic, bank_name="HBL",
                 bank_account_title=name, bank_account_number=f"0012-{code}-01")
        u.set_password("emp123")
        db.session.add(u)
        db.session.flush()
        employees.append(u)

        # Leave quotas
        for lt in leave_types:
            q = LeaveQuota(user_id=u.id, leave_type_id=lt.id, year=date.today().year,
                           total=lt.default_quota, remaining=lt.default_quota)
            db.session.add(q)

        # Payroll profiles
        basics = {"EMP001": 80000, "EMP002": 65000, "EMP003": 70000}
        pp = PayrollProfile(user_id=u.id, basic_salary=basics[code], effective_from=date.today())
        db.session.add(pp)
        db.session.flush()
        db.session.add(PayrollComponent(profile_id=pp.id, name="Medical Allowance", type="allowance",
                                         calculation_method="fixed", value=basics[code] * 0.10))
        db.session.add(PayrollComponent(profile_id=pp.id, name="House Rent", type="allowance",
                                         calculation_method="fixed", value=basics[code] * 0.30))
        db.session.add(PayrollComponent(profile_id=pp.id, name="Fuel Allowance", type="allowance",
                                         calculation_method="fixed", value=5000))
        db.session.add(PayrollComponent(profile_id=pp.id, name="Income Tax", type="deduction",
                                         calculation_method="fixed", value=basics[code] * 0.05))

    # Quotas for admin & manager too
    for lt in leave_types:
        for u in [admin, manager]:
            q = LeaveQuota(user_id=u.id, leave_type_id=lt.id, year=date.today().year,
                           total=lt.default_quota, remaining=lt.default_quota)
            db.session.add(q)

    db.session.commit()
    print("Database seeded successfully!")
    print("Admin: admin@solarkon.com / admin123")
    print("Manager: manager@solarkon.com / mgr123")
    print("Employee: john.doe@solarkon.com / emp123")
