import os
from datetime import date, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from .config import Config
from .extensions import db, login_manager, principals, csrf
from .models.user import Role, Permission


def create_app():
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"), static_url_path="/static")
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    principals.init_app(app)
    csrf.init_app(app)

    from .routes.auth import auth_bp
    from .routes.attendance import attendance_bp
    from .routes.leave import leave_bp
    from .routes.ess import ess_bp
    from .routes.reports import reports_bp
    from .routes.mss import mss_bp
    from .routes.workplace import workplace_bp
    from .routes.timesheet import timesheet_bp
    from .routes.digital_file import df_bp
    from .routes.compensation import comp_bp
    from .routes.communication import comm_bp
    from .routes.pf import pf_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(leave_bp)
    app.register_blueprint(ess_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(mss_bp)
    app.register_blueprint(workplace_bp)
    app.register_blueprint(timesheet_bp)
    app.register_blueprint(df_bp)
    app.register_blueprint(comp_bp)
    app.register_blueprint(comm_bp)
    app.register_blueprint(pf_bp)

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("auth.login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        chart_data = []
        if current_user.is_admin() or current_user.is_manager():
            from .models.attendance import Attendance
            from .models.user import User
            from sqlalchemy import func, extract, case
            import calendar
            yearly = db.session.query(
                extract("week", Attendance.date).label("week"),
                extract("year", Attendance.date).label("year"),
                func.count(Attendance.id).label("total"),
                func.sum(case((Attendance.is_late == True, 1), else_=0)).label("late"),
                func.sum(case((Attendance.is_half_day == True, 1), else_=0)).label("half"),
            ).filter(
                extract("year", Attendance.date) == date.today().year,
                func.strftime("%w", Attendance.date).in_(["1", "2", "3", "4", "5"])
            ).group_by("year", "week").order_by("year", "week").all()
            emp_count = User.query.filter_by(is_active=True).count()
            chart_data = []
            for r in yearly:
                wk = int(r.week)
                yr = int(r.year)
                # SQLite %W week: week 1 starts on first Monday of the year
                jan1 = date(yr, 1, 1)
                first_monday = jan1 + timedelta(days=(7 - jan1.weekday()) % 7)
                monday = first_monday + timedelta(weeks=wk - 1)
                # Count weekdays (Mon-Fri) in that week
                weekdays = sum(1 for d in range(7) if (monday + timedelta(days=d)).weekday() < 5)
                possible = emp_count * weekdays
                pct = round((int(r.total) / possible) * 100, 1) if possible else 0
                chart_data.append({
                    "week": wk, "total": int(r.total), "late": int(r.late), "half": int(r.half),
                    "pct": pct, "label": f"{monday:%b %d}"
                })
        return render_template("dashboard/index.html", chart_data=chart_data)

    @app.context_processor
    def inject_notifications():
        ctx = {}
        if current_user.is_authenticated:
            from .models.communication import NotificationRecipient
            unread_count = NotificationRecipient.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
            recent_notifs = NotificationRecipient.query.filter_by(
                user_id=current_user.id, is_read=False
            ).order_by(NotificationRecipient.id.desc()).limit(5).all()
            ctx.update({"unread_count": unread_count, "recent_notifications": recent_notifs})
        return ctx

    @app.context_processor
    def inject_back_urls():
        ep = request.endpoint or ""
        back_map = {
            "attendance.overview": "attendance.index",
            "leave.apply": "leave.index",
            "leave.calendar": "leave.index",
            "leave.holidays": "leave.index",
            "leave.workflows": "leave.index",
            "timesheet.projects": "timesheet.index",
            "timesheet.merge_report": "timesheet.index",
            "timesheet.merge_report": "timesheet.index",
            "ess.loans": "ess.index",
            "ess.slips": "ess.index",
            "ess.performance": "ess.index",
            "ess.change_requests": "ess.index",
            "digital_files.admin": "digital_files.index",
            "digital_files.profile": "digital_files.index",
            "compensation.revisions": "compensation.index",
            "compensation.view_slip": "compensation.index",
            "pf.config": "pf.index",
            "pf.button_permissions": "pf.index",
            "pf.request_withdrawal": "pf.index",
            "pf.request_loan": "pf.index",
            "mss.approvals": "mss.index",
            "mss.team": "mss.index",
            "mss.team_calendar": "mss.index",
            "mss.evaluate": "mss.team",
            "attendance.admin_view": "attendance.index",
            "attendance.policies": "attendance.index",
            "workplace.announcements": "workplace.index",
            "workplace.events": "workplace.index",
            "workplace.kanban": "workplace.index",
            "auth.change_password": "dashboard",
            "auth.user_add": "auth.user_list",
            "auth.user_edit": "auth.user_list",
        }
        if ep in back_map:
            try:
                return {"back_url": url_for(back_map[ep])}
            except Exception:
                pass
        return {}

    import traceback
    @app.errorhandler(500)
    def handle_500(e):
        tb = traceback.format_exc()
        return f"<pre style='background:#fef2f2;padding:20px;border:2px solid #ef4444;border-radius:8px;font-size:13px;overflow:auto;max-height:90vh;'>{tb}</pre>", 500

    @app.errorhandler(Exception)
    def handle_all(e):
        tb = traceback.format_exc()
        return f"<pre style='background:#fef2f2;padding:20px;border:2px solid #ef4444;border-radius:8px;font-size:13px;overflow:auto;max-height:90vh;'>{tb}</pre>", 500

    with app.app_context():
        db.create_all()
        Role.seed()
        Permission.seed()
        db.session.commit()

    return app


if __name__ == "__main__":
    app = create_app()
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
