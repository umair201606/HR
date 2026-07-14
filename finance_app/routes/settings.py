from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from shared.extensions import db
from shared.models.base import User, Role, Permission
from shared.models.ledger import ChartOfAccount
from shared.models.company_settings import CompanyInfo, AccountingPeriod
from dateutil.relativedelta import relativedelta
from datetime import timedelta

finance_settings_bp = Blueprint("finance_settings", __name__,
                                url_prefix="/finance/settings")


def _require_admin():
    if not current_user.is_admin():
        return False
    return True


# ═══════════════════════════════════════════════
# MAIN SETTINGS PAGE
# ═══════════════════════════════════════════════

@finance_settings_bp.route("/", methods=["GET"])
@login_required
def index():
    tab = request.args.get("tab", "company")
    company = CompanyInfo.get()
    periods = AccountingPeriod.query.order_by(AccountingPeriod.start_date.desc()).all()
    users = User.query.order_by(User.full_name).all() if _require_admin() else []
    roles = Role.query.all() if _require_admin() else []
    accounts = ChartOfAccount.query.filter_by(is_active=True).order_by(ChartOfAccount.code).all()

    resources = sorted(set(
        [p.resource for p in Permission.query.all()] +
        ["attendance", "leaves", "ess", "reports", "mss", "workplace",
         "timesheets", "digital_files", "compensation", "communications",
         "pf", "users", "products", "suppliers", "purchase_invoice",
         "purchase_return", "sales", "inventory", "finance"]
    ))

    return render_template("finance/settings.html", tab=tab, company=company,
                           periods=periods, users=users, roles=roles,
                           accounts=accounts, resources=resources,
                           now=datetime.utcnow())


# ═══════════════════════════════════════════════
# COMPANY PROFILE
# ═══════════════════════════════════════════════

@finance_settings_bp.route("/company", methods=["POST"])
@login_required
def save_company():
    c = CompanyInfo.get()
    c.company_name = request.form.get("company_name", c.company_name)
    c.address = request.form.get("address", "")
    c.city = request.form.get("city", "")
    c.state = request.form.get("state", "")
    c.country = request.form.get("country", "Pakistan")
    c.phone = request.form.get("phone", "")
    c.email = request.form.get("email", "")
    c.website = request.form.get("website", "")
    c.tax_id = request.form.get("tax_id", "")
    c.registration_number = request.form.get("registration_number", "")
    c.fiscal_year_start_month = int(request.form.get("fiscal_year_start_month", 1))
    c.currency = request.form.get("currency", "PKR")
    c.currency_symbol = request.form.get("currency_symbol", "Rs.")
    c.timezone = request.form.get("timezone", "Asia/Karachi")
    db.session.commit()
    flash("Company profile updated", "success")
    return redirect(url_for("finance_settings.index", tab="company"))


# ═══════════════════════════════════════════════
# FINANCIAL PERIODS
# ═══════════════════════════════════════════════

@finance_settings_bp.route("/periods/add", methods=["POST"])
@login_required
def add_period():
    if not _require_admin():
        flash("Access denied", "error")
        return redirect(url_for("finance_settings.index", tab="periods"))
    fy = request.form.get("fiscal_year", "")
    pname = request.form.get("period_name", "")
    sd = request.form.get("start_date", "")
    ed = request.form.get("end_date", "")
    if not all([fy, pname, sd, ed]):
        flash("All fields required", "error")
    else:
        p = AccountingPeriod(fiscal_year=fy, period_name=pname,
                             start_date=datetime.strptime(sd, "%Y-%m-%d").date(),
                             end_date=datetime.strptime(ed, "%Y-%m-%d").date())
        db.session.add(p)
        db.session.commit()
        flash("Period added", "success")
    return redirect(url_for("finance_settings.index", tab="periods"))


@finance_settings_bp.route("/periods/close/<int:id>", methods=["POST"])
@login_required
def close_period(id):
    p = AccountingPeriod.query.get_or_404(id)
    p.is_open = False
    p.is_closed = True
    p.closed_at = datetime.utcnow()
    db.session.commit()
    flash(f"Period '{p.period_name}' closed", "success")
    return redirect(url_for("finance_settings.index", tab="periods"))


@finance_settings_bp.route("/periods/reopen/<int:id>", methods=["POST"])
@login_required
def reopen_period(id):
    p = AccountingPeriod.query.get_or_404(id)
    p.is_open = True
    p.is_closed = False
    p.closed_at = None
    db.session.commit()
    flash(f"Period '{p.period_name}' reopened", "success")
    return redirect(url_for("finance_settings.index", tab="periods"))


@finance_settings_bp.route("/periods/seed", methods=["POST"])
@login_required
def seed_periods():
    AccountingPeriod.seed_current_year()
    flash("Fiscal year periods seeded", "success")
    return redirect(url_for("finance_settings.index", tab="periods"))


# ═══════════════════════════════════════════════
# USER RIGHTS & CONTROLS
# ═══════════════════════════════════════════════

@finance_settings_bp.route("/users/<int:uid>/update-access", methods=["POST"])
@login_required
def update_user_access(uid):
    if not _require_admin():
        return jsonify({"ok": False, "error": "Access denied"}), 403
    u = User.query.get_or_404(uid)
    u.has_hr_access = bool(request.form.get("has_hr_access"))
    u.has_inventory_access = bool(request.form.get("has_inventory_access"))
    db.session.commit()
    flash(f"Access rights updated for {u.full_name}", "success")
    return redirect(url_for("finance_settings.index", tab="rights"))


@finance_settings_bp.route("/users/<int:uid>/deactivate", methods=["POST"])
@login_required
def deactivate_user(uid):
    if not _require_admin():
        return jsonify({"ok": False, "error": "Access denied"}), 403
    u = User.query.get_or_404(uid)
    u.is_active = not u.is_active
    db.session.commit()
    status = "activated" if u.is_active else "deactivated"
    flash(f"{u.full_name} {status}", "success")
    return redirect(url_for("finance_settings.index", tab="rights"))


@finance_settings_bp.route("/permissions/update", methods=["POST"])
@login_required
def update_permissions():
    if not _require_admin():
        flash("Access denied", "error")
        return redirect(url_for("finance_settings.index", tab="rights"))
    role_id = request.form.get("role_id", type=int)
    resource = request.form.get("resource", "")
    can_r = bool(request.form.get("can_read"))
    can_w = bool(request.form.get("can_write"))
    can_d = bool(request.form.get("can_delete"))
    if not role_id or not resource:
        flash("Role and resource required", "error")
        return redirect(url_for("finance_settings.index", tab="rights"))
    perm = Permission.query.filter_by(role_id=role_id, resource=resource).first()
    if perm:
        perm.can_read = can_r
        perm.can_write = can_w
        perm.can_delete = can_d
    else:
        perm = Permission(role_id=role_id, resource=resource,
                          can_read=can_r, can_write=can_w, can_delete=can_d)
        db.session.add(perm)
    db.session.commit()
    flash(f"Permissions updated for {resource}", "success")
    return redirect(url_for("finance_settings.index", tab="rights"))
