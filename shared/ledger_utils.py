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


def get_or_create_account(code, name, type_):
    acct = ChartOfAccount.query.filter_by(code=code).first()
    if not acct:
        acct = ChartOfAccount(code=code, name=name, type=type_)
        db.session.add(acct)
        db.session.flush()
    return acct
