from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@login_required
def hub():
    has_hr = current_user.has_hr_access or current_user.is_admin()
    has_inv = current_user.has_inventory_access or current_user.is_admin()
    if not has_hr and not has_inv:
        return render_template("dashboard/access_denied.html")
    return render_template("dashboard/hub.html",
                           has_hr=has_hr, has_inv=has_inv)
