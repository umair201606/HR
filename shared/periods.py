"""Accounting period locking.

A closed period is frozen: its reported numbers must never move again. That is
what makes a cost, once computed and conveyed, permanent — an employee charged
for a damaged product has an agreed receivable, and if a later edit could still
shift the period the charge sits in, "agreed" means nothing.

Two paths can move a closed period's numbers, and both are guarded here:

    posting     a new journal entry dated inside the period.
    un-posting  reverse_journal_entry flips is_posted=False on the ORIGINAL
                entry rather than writing a counter-entry, so un-approving a
                voucher silently rewrites the period it was posted in.

The rule is the one every serious ERP applies: corrections to a closed period
are not made in that period. They are posted as an adjusting entry in the
current open period, where they are visible.
"""

from datetime import date, datetime

from shared.models.company_settings import AccountingPeriod


class ClosedPeriodError(Exception):
    """Raised when an operation would change a closed period's numbers."""


def _as_date(when):
    if isinstance(when, datetime):
        return when.date()
    if isinstance(when, date):
        return when
    return date.today()


def period_for(when):
    """The accounting period covering ``when``, or None if none is defined."""
    d = _as_date(when)
    return (AccountingPeriod.query
            .filter(AccountingPeriod.start_date <= d,
                    AccountingPeriod.end_date >= d)
            .order_by(AccountingPeriod.start_date.desc())
            .first())


def current_open_period():
    """The open period covering today, if any — where corrections belong."""
    p = period_for(date.today())
    return p if (p is not None and not p.is_closed) else None


def is_closed(when):
    p = period_for(when)
    return p is not None and bool(p.is_closed)


def require_open_period(when, action="post to"):
    """Refuse if ``when`` falls in a closed period.

    A date no period covers is allowed: periods are created by the user, and
    refusing every date outside them would block posting on a fresh database
    that has only the current fiscal year seeded. Only an explicit close locks.
    """
    p = period_for(when)
    if p is None or not p.is_closed:
        return p
    closed_on = p.closed_at.strftime("%d %b %Y") if p.closed_at else "earlier"
    raise ClosedPeriodError(
        f"Cannot {action} {_as_date(when).strftime('%d %b %Y')}: the period "
        f"'{p.period_name}' ({p.start_date:%d %b %Y} – {p.end_date:%d %b %Y}) "
        f"was closed on {closed_on} and its figures are final. Post an "
        f"adjusting entry in the current open period instead, or reopen "
        f"'{p.period_name}' in Settings → Periods if closing it was a mistake."
    )
