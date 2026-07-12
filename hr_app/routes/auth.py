from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db, csrf
from ..models.user import User, Role
from ..models.communication import Notification, NotificationRecipient

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_active:
                flash("Your account has been deactivated.", "danger")
                return render_template("login.html")
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile")
@login_required
def profile():
    return render_template("ess/profile.html", user=current_user)


@auth_bp.route("/api/notifications")
@login_required
def api_notifications():
    recipients = NotificationRecipient.query.filter_by(
        user_id=current_user.id, is_read=False
    ).order_by(NotificationRecipient.id.desc()).limit(20).all()
    return jsonify([{
        "id": r.id,
        "title": r.notification.title,
        "message": r.notification.message,
        "type": r.notification.notification_type,
        "module": r.notification.module,
        "created_at": r.notification.created_at.isoformat()
    } for r in recipients])


@auth_bp.route("/api/notifications/<int:nid>/read", methods=["POST"])
@csrf.exempt
@login_required
def mark_notification_read(nid):
    r = NotificationRecipient.query.filter_by(id=nid, user_id=current_user.id).first()
    if r:
        r.is_read = True
        r.read_at = datetime.utcnow()
        db.session.commit()
    return jsonify({"success": True})


@auth_bp.route("/api/notifications/read-all", methods=["POST"])
@csrf.exempt
@login_required
def mark_all_read():
    NotificationRecipient.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({"is_read": True, "read_at": datetime.utcnow()})
    db.session.commit()
    return jsonify({"success": True})
