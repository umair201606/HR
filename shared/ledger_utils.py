from decimal import Decimal
from shared.extensions import db
from shared.models.ledger import JournalEntry, JournalLine, ChartOfAccount


def post_journal_entry(voucher_type, voucher_id, voucher_number, description,
                       lines, entry_date=None, created_by=1):
    from datetime import datetime
    je = JournalEntry(
        voucher_type=voucher_type,
        voucher_id=voucher_id,
        voucher_number=voucher_number,
        description=description,
        entry_date=entry_date or datetime.utcnow(),
        created_by=created_by
    )
    db.session.add(je)
    db.session.flush()

    for line in lines:
        jl = JournalLine(
            journal_entry_id=je.id,
            account_id=line["account_id"],
            debit=Decimal(str(line.get("debit", 0))),
            credit=Decimal(str(line.get("credit", 0))),
            description=line.get("description", "")
        )
        db.session.add(jl)
    db.session.flush()
    return je


def reverse_journal_entry(voucher_type, voucher_id, created_by=1):
    entries = JournalEntry.query.filter_by(
        voucher_type=voucher_type, voucher_id=voucher_id
    ).all()
    for entry in entries:
        entry.is_posted = False
    db.session.flush()

    for entry in entries:
        lines = []
        for line in entry.lines:
            lines.append({
                "account_id": line.account_id,
                "debit": line.credit,
                "credit": line.debit,
                "description": f"Reversal: {line.description}"
            })
        je = JournalEntry(
            voucher_type=voucher_type,
            voucher_id=voucher_id,
            voucher_number=entry.voucher_number + "-REV",
            description=f"Reversal of {entry.voucher_number}",
            entry_date=entry.entry_date,
            created_by=created_by,
            is_posted=True
        )
        db.session.add(je)
        db.session.flush()
        for line in lines:
            jl = JournalLine(
                journal_entry_id=je.id,
                account_id=line["account_id"],
                debit=Decimal(str(line["debit"])),
                credit=Decimal(str(line["credit"])),
                description=line["description"]
            )
            db.session.add(jl)
    db.session.flush()


def get_account_by_code(code):
    return ChartOfAccount.query.filter_by(code=code).first()


def get_or_create_account(code, name, type_, parent_code=None):
    acct = ChartOfAccount.query.filter_by(code=str(code)).first()
    if not acct:
        parent = None
        if parent_code:
            parent = ChartOfAccount.query.filter_by(code=str(parent_code)).first()
        if not parent:
            # Auto-discover parent by type hierarchy
            coa_type_map = {"asset": "Assets", "liability": "Liabilities", "equity": "Equity",
                            "revenue": "Revenue", "expense": "Expense", "contra-expense": "Expense"}
            l1_name = coa_type_map.get(type_)
            if l1_name:
                l1 = ChartOfAccount.query.filter_by(name=l1_name, level=1).first()
                if l1:
                    l2 = ChartOfAccount.query.filter_by(parent_id=l1.id, level=2).first()
                    if l2:
                        parent = ChartOfAccount.query.filter_by(parent_id=l2.id, level=3).first()
        acct = ChartOfAccount(code=str(code), name=name, type=type_,
                              parent_id=parent.id if parent else None,
                              level=4)
        db.session.add(acct)
        db.session.flush()
    return acct
