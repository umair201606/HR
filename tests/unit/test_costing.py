"""Costing engine: cost accuracy, immutability of posted cost, and the
layer/ledger invariant that keeps inventory tied to COGS.

The scenario these are built around is a product bought at several prices
over time, sold at several prices, and scrapped or charged to an employee —
with the valuation method switched partway and a historic voucher deleted.
"""

from decimal import Decimal

import pytest

from shared.extensions import db
from shared import costing
from shared.costing import NegativeStockError
from shared.models.stock_ledger import StockLedger
from shared.models.stock_layer import StockLayer, LayerConsumption


def buy(qty, unit_cost, n=1):
    return costing.record_in(1, "PI", n, f"PI-{n:05d}", qty=qty, unit_cost=unit_cost)


def issue(qty, n=1, vtype="SI", **kw):
    return costing.record_out(1, vtype, n, f"{vtype}-{n:05d}", qty=qty, **kw)


def book_value():
    _qty, cost, _avg = StockLedger.get_running_balance(1)
    return Decimal(str(cost))


def assert_ties(msg=""):
    """Layers must always back the ledger; drift is money invented or lost."""
    ok, layer_value, running_cost = costing.assert_invariant(1)
    assert ok, (f"{msg}: layers value {layer_value} != ledger running_cost "
                f"{running_cost} — inventory no longer ties to COGS")


# ─────────────────────────────────────────────
# Cost accuracy across multiple prices
# ─────────────────────────────────────────────

def test_weighted_average_issues_at_running_average(settings, product):
    buy(10, 10, n=1)          # 100
    buy(10, 20, n=2)          # 200 -> 20 units / 300 / avg 15
    unit, total = issue(10)
    assert unit == Decimal("15.0000")
    assert total == Decimal("150.00")
    assert book_value() == Decimal("150.0000")
    assert_ties("after WA issue")


def test_weighted_average_reaverages_on_each_receipt(settings, product):
    buy(10, 10, n=1)
    assert costing.current_unit_cost(1) == Decimal("10.0000")
    buy(30, 20, n=2)          # 40 units / 700 -> avg 17.50
    assert costing.current_unit_cost(1) == Decimal("17.5000")
    # One pool under weighted average, never a queue of layers.
    assert len(costing.layers_remaining(1)) == 1
    assert_ties("after re-average")


def test_fifo_issues_oldest_layer_first(settings, product):
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    unit, total = issue(10)
    assert unit == Decimal("10.0000"), "FIFO must take the oldest layer"
    assert total == Decimal("100.00")
    assert costing.layers_remaining(1) == [(Decimal("20.0000"), Decimal("10.0000"))]
    assert_ties("after FIFO issue")


def test_fifo_issue_spanning_layers_blends_cost(settings, product):
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    unit, total = issue(15)   # 10 @ 10 + 5 @ 20 = 200 over 15 units
    assert total == Decimal("200.00")
    assert unit == Decimal("13.3333")
    assert_ties("after spanning issue")


def test_scrap_and_consumption_issue_at_historic_cost(settings, product):
    buy(10, 10, n=1)
    buy(10, 20, n=2)          # avg 15
    unit, total = issue(4, n=1, vtype="SCRAP")
    assert unit == Decimal("15.0000")
    assert total == Decimal("60.00")
    unit, total = issue(4, n=1, vtype="CONS")
    assert unit == Decimal("15.0000")
    assert_ties("after scrap + consumption")


# ─────────────────────────────────────────────
# Switching valuation method
# ─────────────────────────────────────────────

def test_method_switch_preserves_book_value(settings, product):
    """The original defect: buy at two prices, sell under WA, switch to FIFO.

    The old engine re-derived FIFO layers by replaying OUT quantities against
    IN rows, so it "saw" the untouched 10 @ 20 layer (value 200) even though
    the books said 150 — then charged 200 to COGS, expensing 350 against
    purchases of 300.
    """
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    _u, first_cogs = issue(10)                 # WA: 10 @ 15 = 150
    assert first_cogs == Decimal("150.00")
    assert book_value() == Decimal("150.0000")

    costing.revalue_for_method_change("fifo")
    settings.valuation_method = "fifo"
    db.session.commit()

    assert costing.stock_value(1) == Decimal("150.0000"), \
        "revaluation must carry stock at book value, not re-derive it"
    assert_ties("immediately after switch to FIFO")

    _u, second_cogs = issue(10, n=2)
    assert second_cogs == Decimal("150.00"), \
        "the remaining 10 units are worth 150, whatever the method"

    purchases = Decimal("300.00")
    assert first_cogs + second_cogs == purchases, \
        "total COGS must equal total purchases once stock is exhausted"
    assert costing.on_hand(1) == 0
    assert book_value() == 0


def test_method_switch_does_not_change_already_posted_costs(settings, product):
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    issue(10)
    posted = [(r.id, r.unit_cost, r.total_cost)
              for r in StockLedger.query.order_by(StockLedger.id).all()]

    costing.revalue_for_method_change("fifo")
    settings.valuation_method = "fifo"
    db.session.commit()

    after = [(r.id, r.unit_cost, r.total_cost)
             for r in StockLedger.query.order_by(StockLedger.id).all()]
    assert after == posted, "a method switch must never restate a posted cost"


def test_fifo_to_weighted_average_collapses_layers_at_book_value(settings, product):
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    assert len(costing.layers_remaining(1)) == 2

    costing.revalue_for_method_change("weighted_average")
    settings.valuation_method = "weighted_average"
    db.session.commit()

    layers = costing.layers_remaining(1)
    assert len(layers) == 1, "weighted average holds a single pool"
    assert layers[0] == (Decimal("15.0000"), Decimal("20.0000"))
    assert_ties("after FIFO -> WA collapse")


def test_ledger_rows_record_the_method_that_priced_them(settings, product):
    buy(10, 10, n=1)
    issue(5)
    costing.revalue_for_method_change("fifo")
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 20, n=2)
    issue(5, n=2)

    rows = StockLedger.query.order_by(StockLedger.id).all()
    assert [r.valuation_method for r in rows] == [
        "weighted_average", "weighted_average", "fifo", "fifo"]


# ─────────────────────────────────────────────
# Immutability of a posted charge
# ─────────────────────────────────────────────

def test_employee_receivable_survives_later_activity(settings, product):
    """Charge an employee for a damaged unit, then keep trading the product.

    The agreed receivable must never move: it was conveyed to a person.
    """
    buy(10, 10, n=1)
    charged_unit, charged_total = issue(1, n=1, vtype="SCRAP")
    assert charged_total == Decimal("10.00")

    scrap_row = StockLedger.query.filter_by(voucher_type="SCRAP").one()

    buy(50, 99, n=2)          # wildly different price
    issue(20, n=2)
    costing.revalue_for_method_change("fifo")
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(5, 3, n=3)
    issue(2, n=3, vtype="CONS")

    db.session.refresh(scrap_row)
    assert scrap_row.unit_cost == charged_unit
    assert scrap_row.total_cost == charged_total, \
        "the employee's agreed receivable moved after later activity"


def test_consumption_records_which_purchases_backed_the_charge(settings, product):
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    issue(15, n=1, vtype="CONS")   # eats all of layer 1 and half of layer 2

    out_row = StockLedger.query.filter_by(voucher_type="CONS").one()
    cons = LayerConsumption.query.filter_by(out_ledger_id=out_row.id).all()
    assert len(cons) == 2, "an issue spanning two layers records both"
    assert sum(c.total_cost for c in cons) == out_row.total_cost, \
        "the audit trail must add up to the posted cost"


# ─────────────────────────────────────────────
# Negative stock
# ─────────────────────────────────────────────

def test_issuing_more_than_on_hand_is_refused(settings, product):
    buy(5, 10, n=1)
    with pytest.raises(NegativeStockError, match="only"):
        issue(10)
    assert costing.on_hand(1) == 5, "the refused issue must not move stock"
    assert_ties("after refused issue")


def test_negative_stock_allowed_when_configured(settings, product):
    settings.allow_negative_stock = True
    db.session.commit()
    buy(5, 10, n=1)
    unit, total = issue(10)
    assert unit == Decimal("10.0000"), "uncovered units fall back to last cost"
    assert costing.on_hand(1) == -5


# ─────────────────────────────────────────────
# Reversal
# ─────────────────────────────────────────────

def test_reversing_an_issue_gives_back_the_layer_quantity(settings, product):
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    issue(10, n=1)
    assert costing.layers_remaining(1) == [(Decimal("20.0000"), Decimal("10.0000"))]

    costing.reverse_voucher_stock("SI", 1)
    db.session.commit()

    assert costing.layers_remaining(1) == [(Decimal("10.0000"), Decimal("10.0000")),
                                           (Decimal("20.0000"), Decimal("10.0000"))]
    assert costing.on_hand(1) == 20
    assert_ties("after reversing an issue")
    assert LayerConsumption.query.count() == 0


def test_reversing_a_receipt_withdraws_its_layer(settings, product):
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)

    costing.reverse_voucher_stock("PI", 2)
    db.session.commit()

    assert costing.layers_remaining(1) == [(Decimal("10.0000"), Decimal("10.0000"))]
    assert costing.on_hand(1) == 10
    assert_ties("after reversing a receipt")


def test_reversing_a_consumed_receipt_is_refused(settings, product):
    """Deleting a purchase whose stock was already issued.

    The issue posted a COGS of 100 drawn from this receipt. Withdrawing the
    receipt would leave that frozen 100 backed by a purchase that no longer
    exists, with the quantity silently re-drawn from the 20-cost layer. The
    old engine allowed it and drove running_cost to -200 on 0 units.
    """
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    issue(10, n=1)            # eats layer 1 entirely

    with pytest.raises(costing.ConsumedLayerError, match="already been issued"):
        costing.reverse_voucher_stock("PI", 1)

    assert costing.on_hand(1) == 10, "the refused reversal must not move stock"
    assert_ties("after refused reversal")


def test_consumed_receipt_reversible_once_its_issue_is_reversed(settings, product):
    """The documented way out: reverse the dependent issue, then the receipt."""
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    issue(10, n=1)

    costing.reverse_voucher_stock("SI", 1)     # give the quantity back first
    db.session.commit()
    costing.reverse_voucher_stock("PI", 1)     # now the layer is untouched
    db.session.commit()

    assert costing.layers_remaining(1) == [(Decimal("20.0000"), Decimal("10.0000"))]
    assert costing.on_hand(1) == 10
    assert_ties("after reversing issue then receipt")


def test_reversing_a_merged_weighted_average_receipt_ties(settings, product):
    """Weighted-average receipts merge into the pool instead of opening a layer.

    Reversal has no layer to withdraw by source_ledger_id, so the pool has to
    be re-pointed at the ledger — otherwise the ledger drops the value and the
    layer keeps it (a reversed 10 @ 20 left a layer worth 300 against a
    ledger of 100).
    """
    buy(10, 10, n=1)
    buy(10, 20, n=2)          # merges -> one pool of 20 @ 15
    assert len(costing.layers_remaining(1)) == 1

    costing.reverse_voucher_stock("PI", 2)
    db.session.commit()

    assert costing.on_hand(1) == 10
    assert costing.layers_remaining(1) == [(Decimal("10.0000"), Decimal("10.0000"))], \
        "the pool must fall back to the surviving receipt's cost"
    assert_ties("after reversing a merged WA receipt")


def test_reversing_a_consumed_weighted_average_receipt_is_refused(settings, product):
    """WA stock is fungible, so no layer records who consumed the receipt.

    Withdrawing more than remains on hand necessarily takes back units already
    issued at a now-frozen cost. Unrefused, this drove stock to -5.
    """
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    issue(15, n=1)            # 5 left on hand; PI-2 brought in 10

    with pytest.raises(costing.ConsumedLayerError, match="remain on hand"):
        costing.reverse_voucher_stock("PI", 2)

    assert costing.on_hand(1) == 5, "the refused reversal must not move stock"
    assert_ties("after refused WA reversal")


def test_reversing_an_issue_under_weighted_average_ties(settings, product):
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    issue(8, n=1)

    costing.reverse_voucher_stock("SI", 1)
    db.session.commit()

    assert costing.on_hand(1) == 20
    assert costing.layers_remaining(1) == [(Decimal("15.0000"), Decimal("20.0000"))]
    assert_ties("after reversing a WA issue")


# ─────────────────────────────────────────────
# Variance: deleting a consumed receipt anyway
# ─────────────────────────────────────────────

def test_variance_lets_a_consumed_receipt_be_reversed(settings, product):
    """The case that is refused without allow_variance.

    Buy 10 @ 10 and 10 @ 20, sell 10 (FIFO: COGS 100 from the first layer),
    then delete the 10 @ 10 purchase. It never happened — but 100 was posted
    against it and conveyed. The 10 units sold must now come out of the 20-cost
    layer, which is worth 200, while the posted COGS stays 100. The 100 gap is
    the variance.
    """
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    _u, cogs = issue(10, n=1)
    assert cogs == Decimal("100.00")

    variances = costing.reverse_voucher_stock("PI", 1, allow_variance=True)
    db.session.commit()

    assert variances[1] == Decimal("100.00"), \
        "200 of surviving purchase, 100 expensed, nothing left = 100 unhomed"
    assert costing.on_hand(1) == 0
    assert costing.stock_value(1) == 0
    assert_ties("after reversing a consumed receipt with a variance")

    sale = StockLedger.query.filter_by(voucher_type="SI").one()
    assert sale.total_cost == cogs, "the posted COGS must not be restated"


def test_variance_writes_a_value_only_ledger_row(settings, product):
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    issue(10, n=1)
    costing.reverse_voucher_stock("PI", 1, allow_variance=True)
    db.session.commit()

    var = StockLedger.query.filter_by(voucher_type="VAR").one()
    assert var.quantity == 0, "a variance moves value, not stock"
    assert var.total_cost == Decimal("100.00")
    assert "no remaining purchase" in var.notes


def test_no_variance_when_the_reversed_receipt_was_untouched(settings, product):
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)

    variances = costing.reverse_voucher_stock("PI", 2, allow_variance=True)
    db.session.commit()

    assert variances == {}, "nothing consumed it, so nothing is unaccounted for"
    assert StockLedger.query.filter_by(voucher_type="VAR").count() == 0
    assert_ties("after a clean reversal under allow_variance")


def test_weighted_average_absorbs_the_gap_into_the_surviving_units(settings, product):
    """Under WA the pool re-averages rather than writing off.

    Buy 10 @ 10 and 10 @ 20 (pool 20 @ 15), sell 5 at 15, then delete the
    10 @ 10 purchase. 200 was bought and 75 expensed, so the 5 units left carry
    125 — an average of 25. The posted 75 does not move; the future re-prices.
    """
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    _u, cogs = issue(5, n=1)
    assert cogs == Decimal("75.00")

    variances = costing.reverse_voucher_stock("PI", 1, allow_variance=True)
    db.session.commit()

    assert variances == {}, "with units left, WA re-averages instead"
    assert costing.on_hand(1) == 5
    assert costing.current_unit_cost(1) == Decimal("25.0000")
    assert_ties("after WA absorbs the gap")

    sale = StockLedger.query.filter_by(voucher_type="SI").one()
    assert sale.total_cost == cogs, "the posted COGS must not be restated"


def test_weighted_average_writes_off_when_no_units_remain(settings, product):
    """With nothing left to absorb the gap, WA must write it off.

    The qty==0 clamp zeroes running_cost, so a variance computed from
    running_cost would read zero here while 50 is genuinely unaccounted for.
    """
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    issue(10, n=1)            # WA: 10 @ 15 = 150 posted

    variances = costing.reverse_voucher_stock("PI", 1, allow_variance=True)
    db.session.commit()

    assert costing.on_hand(1) == 0
    assert variances[1] == Decimal("50.00"), \
        "200 bought, 150 expensed, nothing on hand = 50 unhomed"
    assert_ties("after WA write-off")


def test_reversal_still_refuses_by_default(settings, product):
    """allow_variance is opt-in: the safe path stays the default."""
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    buy(10, 20, n=2)
    issue(10, n=1)

    with pytest.raises(costing.ConsumedLayerError):
        costing.reverse_voucher_stock("PI", 1)


def test_reversal_names_the_vouchers_that_consumed_the_stock(settings, product):
    settings.valuation_method = "fifo"
    db.session.commit()
    buy(10, 10, n=1)
    issue(4, n=1, vtype="CONS")
    issue(3, n=2, vtype="SCRAP")

    with pytest.raises(costing.ConsumedLayerError) as exc:
        costing.reverse_voucher_stock("PI", 1)
    assert "CONS-00001" in str(exc.value)
    assert "SCRAP-00002" in str(exc.value)
    assert len(exc.value.dependents) == 2
