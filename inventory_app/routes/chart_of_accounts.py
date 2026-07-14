from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.chart_of_account import ChartOfAccount

inv_coa_bp = Blueprint("inv_chart_of_accounts", __name__,
                        url_prefix="/inventory/chart-of-accounts")


@inv_coa_bp.route("/")
@login_required
def list_accounts():
    accounts = ChartOfAccount.query.order_by(ChartOfAccount.code).all()
    return render_template("chart_of_accounts/list.html", accounts=accounts)


@inv_coa_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_account():
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        type_ = request.form.get("type", "").strip()
        if not code or not name or not type_:
            flash("Code, Name, and Type are required.", "error")
            return redirect(url_for("inv_chart_of_accounts.add_account"))
        if ChartOfAccount.query.filter_by(code=code).first():
            flash(f"Account code {code} already exists.", "error")
            return redirect(url_for("inv_chart_of_accounts.add_account"))
        parent_id = request.form.get("parent_id", type=int) or None
        desc = request.form.get("description", "")
        acct = ChartOfAccount(code=code, name=name, type=type_,
                              parent_id=parent_id, description=desc)
        db.session.add(acct)
        db.session.commit()
        flash(f"Account {code} - {name} created.", "success")
        return redirect(url_for("inv_chart_of_accounts.list_accounts"))
    parents = ChartOfAccount.query.order_by(ChartOfAccount.code).all()
    return render_template("chart_of_accounts/form.html", account=None, parents=parents,
                           types=["asset", "liability", "equity", "revenue", "expense"])


@inv_coa_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_account(id):
    acct = ChartOfAccount.query.get_or_404(id)
    if request.method == "POST":
        acct.code = request.form.get("code", acct.code).strip()
        acct.name = request.form.get("name", acct.name).strip()
        acct.type = request.form.get("type", acct.type).strip()
        acct.parent_id = request.form.get("parent_id", type=int) or None
        acct.description = request.form.get("description", "")
        acct.is_active = request.form.get("is_active") == "1"
        db.session.commit()
        flash(f"Account {acct.code} updated.", "success")
        return redirect(url_for("inv_chart_of_accounts.list_accounts"))
    parents = ChartOfAccount.query.filter(ChartOfAccount.id != id).order_by(ChartOfAccount.code).all()
    return render_template("chart_of_accounts/form.html", account=acct, parents=parents,
                           types=["asset", "liability", "equity", "revenue", "expense"])
