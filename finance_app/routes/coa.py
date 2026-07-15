from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from shared.extensions import db
from shared.models.ledger import ChartOfAccount

coa_bp = Blueprint("coa", __name__, url_prefix="/accounting/coa",
                   template_folder="../../finance_app/templates")

LEVEL_LABELS = {1: "Level 1 — Account Class", 2: "Level 2 — Account Group",
                3: "Level 3 — Account Head", 4: "Level 4 — Account"}


def _tree():
    """Return accounts structured as a flat list with depth info for template rendering."""
    all_accts = ChartOfAccount.query.order_by(ChartOfAccount.code).all()
    acct_map = {a.id: a for a in all_accts}
    roots = [a for a in all_accts if a.parent_id is None]
    rows = []

    def walk(node, depth):
        rows.append({"acct": node, "depth": depth})
        for child in sorted(
            [a for a in all_accts if a.parent_id == node.id],
            key=lambda x: x.code,
        ):
            walk(child, depth + 1)

    for r in sorted(roots, key=lambda x: x.code):
        walk(r, 0)
    return rows


@coa_bp.route("/")
@login_required
def list_accounts():
    return render_template("accounting/coa_list.html", tree=_tree(),
                           level_labels=LEVEL_LABELS)


@coa_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_account():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        parent_id = request.form.get("parent_id", type=int)
        desc = request.form.get("description", "")
        if not name:
            flash("Account name is required.", "error")
            return redirect(url_for("coa.add_account"))
        parent = ChartOfAccount.query.get(parent_id) if parent_id else None
        if not parent:
            flash("Parent account is required.", "error")
            return redirect(url_for("coa.add_account"))
        level = parent.level + 1 if parent and parent.level < 4 else 4
        if level > 4:
            flash("Cannot add children to a Level 4 account.", "error")
            return redirect(url_for("coa.add_account"))
        if parent.is_fixed and level == 2 and parent.name in ("Assets", "Liabilities", "Equity", "Revenue", "Expense"):
            existing_codes = [c.code for c in parent.children]
            used = set(int(c) for c in existing_codes if c.isdigit())
            n = max(used) + 1 if used else int(parent.code) * 10 + 1
            code = str(n)
        else:
            existing_codes = [c.code for c in parent.children]
            max_code = 0
            for c in existing_codes:
                try:
                    max_code = max(max_code, int(c))
                except ValueError:
                    continue
            code = str(max_code + 1) if max_code > 0 else parent.code + "1"

        type_ = parent.type
        acct = ChartOfAccount(code=code, name=name, type=type_,
                              parent_id=parent.id, level=level, description=desc)
        db.session.add(acct)
        db.session.commit()
        flash(f"{LEVEL_LABELS.get(level, 'Account')} \"{name}\" created.", "success")
        return redirect(url_for("coa.list_accounts"))

    parent_id = request.args.get("parent_id", type=int)
    parents = ChartOfAccount.query.filter(ChartOfAccount.level.in_([1, 2, 3]))\
        .order_by(ChartOfAccount.code).all()
    l1 = [a for a in parents if a.level == 1]
    return render_template("accounting/coa_form.html", account=None,
                           parents=parents, l1=l1, parent_id=parent_id,
                           level_labels=LEVEL_LABELS)


@coa_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_account(id):
    acct = ChartOfAccount.query.get_or_404(id)
    if request.method == "POST":
        if acct.is_fixed:
            flash(f"\"{acct.name}\" is a fixed account and cannot be edited.", "error")
            return redirect(url_for("coa.edit_account", id=id))
        acct.name = request.form.get("name", acct.name).strip()
        acct.description = request.form.get("description", "")
        acct.is_active = request.form.get("is_active") == "1"
        db.session.commit()
        flash(f"Account \"{acct.name}\" updated.", "success")
        return redirect(url_for("coa.list_accounts"))
    parents = ChartOfAccount.query.filter(ChartOfAccount.id != id,
                                          ChartOfAccount.level.in_([1, 2, 3]))\
        .order_by(ChartOfAccount.code).all()
    l1 = [a for a in parents if a.level == 1]
    return render_template("accounting/coa_form.html", account=acct,
                           parents=parents, l1=l1, parent_id=acct.parent_id,
                           level_labels=LEVEL_LABELS)


@coa_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete_account(id):
    acct = ChartOfAccount.query.get_or_404(id)
    if not acct.can_delete():
        if acct.is_fixed:
            flash(f"\"{acct.name}\" is a fixed account and cannot be deleted.", "error")
        else:
            flash(f"\"{acct.name}\" has child accounts. Delete children first.", "error")
        return redirect(url_for("coa.list_accounts"))
    db.session.delete(acct)
    db.session.commit()
    flash(f"Account \"{acct.name}\" deleted.", "success")
    return redirect(url_for("coa.list_accounts"))


@coa_bp.route("/api/children")
@login_required
def api_children():
    parent_id = request.args.get("parent_id", type=int)
    if not parent_id:
        return jsonify([])
    children = ChartOfAccount.query.filter_by(parent_id=parent_id).order_by(ChartOfAccount.code).all()
    return jsonify([{"id": c.id, "code": c.code, "name": c.name,
                     "level": c.level, "is_fixed": c.is_fixed,
                     "has_children": ChartOfAccount.query.filter_by(parent_id=c.id).count() > 0}
                    for c in children])


@coa_bp.route("/api/level-accounts")
@login_required
def api_level_accounts():
    level = request.args.get("level", type=int)
    parent_id = request.args.get("parent_id", type=int)
    q = ChartOfAccount.query.filter_by(level=level)
    if parent_id:
        q = q.filter_by(parent_id=parent_id)
    accounts = q.order_by(ChartOfAccount.code).all()
    return jsonify([{"id": a.id, "code": a.code, "name": a.name} for a in accounts])
