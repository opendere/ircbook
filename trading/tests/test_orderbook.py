from decimal import Decimal as D
from random import randint

import pytest

from trading.orderbook import OrderBook, Order, AccountOrders, InstrumentOrders


def test_order_creation_validation():
    """"Tests for the Order constructor."""
    with pytest.raises(ValueError):
        Order(0, Order.ask, "instrument", D(1), D(1))
    with pytest.raises(ValueError):
        Order("account", Order.bid, 0, D(1), D(1))
    with pytest.raises(ValueError):
        Order("account", "c", "instrument", D(1), D(1))
    with pytest.raises(ValueError):
        Order("account", Order.bid, "instrument", D(0), D(1))
    with pytest.raises(ValueError):
        Order("account", Order.bid, "instrument", D(1), D(0))
    with pytest.raises(ValueError):
        Order("account", Order.bid, "instrument", 0, D(1))
    with pytest.raises(ValueError):
        Order("account", Order.bid, "instrument", D(1), 0)
    with pytest.raises(ValueError):
        Order("account", Order.bid, "instrument", D(1), D(1), rank=-1)


def test_order_creation():
    o1 = Order("account", Order.bid, "instrument", D(37), D(11), rank=53)
    o2 = Order("account", Order.bid, "instrument", D(37), D(11))
    for o in [o1, o2]:
        assert (o.account_id == "account")
        assert (o.side == Order.bid)
        assert (o.instrument_id == "instrument")
        assert (o.price == D(37))
        assert (o.num_shares == D(11))
    assert (o1.rank == 53)
    assert (o2.rank is None)


def test_order_matching():
    o1 = Order("u1", Order.ask, "i1", D(30), D(10))
    o2 = Order("u1", Order.bid, "i1", D(31), D(10))
    assert (o1.matches(o2))
    o1.side = Order.bid
    assert (not o1.matches(o2))
    o2.side = Order.ask
    assert (not o1.matches(o2))
    o2.price = D(29)
    assert (o1.matches(o2))
    o1.instrument_id = "i2"
    assert (not o1.matches(o2))


def test_matching_is_commutative():
    o = Order("u", Order.bid, "i", D(40), D(10))
    for i in range(1000):
        price = D(randint(1, 99))
        amount = D(randint(1, 100))
        side = (Order.bid if randint(0, 1) == 0 else Order.ask)
        o2 = Order("u", side, "i", price, amount)
        assert (o.matches(o2) == o2.matches(o))


def test_instrument_add_order():
    i = InstrumentOrders()
    assert (not i.get_asks() and not i.get_bids())
    o_bid = Order("u", Order.bid, "i", D(51), D(1))
    i.add(o_bid)
    assert (o_bid.rank == 0)
    assert (i.get_best_bid() == D(51))
    o_ask = Order("u", Order.ask, "i", D(49), D(10))
    i.add(o_ask)
    assert (o_ask.rank == 1)
    assert (i.get_best_ask() == D(49))
    assert (o_bid in i.get_bids() and o_ask in i.get_asks())
    o_bid2 = Order("u", Order.bid, "i", D(52), D(1))
    i.add(o_bid2)
    assert (i.get_best_bid() == D(52))
    o_bid3 = Order("u", Order.bid, "i", D(42), D(1))
    i.add(o_bid3)
    assert (i.get_best_bid() == D(52))
    o_ask2 = Order("u", Order.ask, "i", D(48), D(10))
    i.add(o_ask2)
    assert (i.get_best_ask() == D(48))
    o_ask3 = Order("u", Order.ask, "i", D(58), D(10))
    i.add(o_ask3)
    assert (i.get_best_ask() == D(48))
    o_n = Order("u", Order.ask, "i", D(18), D(92), rank=101)
    i.add(o_n)
    assert (o_n.rank == 101)


def test_orderbook_add_order():
    ob = OrderBook()
    assert (ob.get_by_instrument_id("i") is None)
    assert (ob.get_by_account_id("u") is None)
    o = Order("u", Order.ask, "i", D(50), D(10))
    o2 = Order("u", Order.bid, "i", D(50), D(10))
    ob.add_order(o)
    ob.add_order(o2)
    assert (isinstance(ob.get_by_instrument_id("i"), InstrumentOrders))
    assert (isinstance(ob.get_by_account_id("u"), AccountOrders))
    assert (o in ob.get_by_instrument_id("i").get_asks())
    assert (o in ob.get_by_account_id("u").asks)
    assert (o2 in ob.get_by_instrument_id("i").get_bids())
    assert (o2 in ob.get_by_account_id("u").bids)


def test_orderbook_remove():
    ob = OrderBook()
    o = Order("u", Order.ask, "i", D(28), D(10))
    ob.add_order(o)
    ob.remove_order(o)
    assert (ob.get_by_instrument_id("i").get_best_ask() is None)
    assert (not ob.get_by_instrument_id("i").get_asks())
    assert (not ob.get_by_account_id("u").asks)


def test_orderbook_remove_shares():
    ob = OrderBook()
    o = Order("u", Order.bid, "i", D(10), D(100))
    ob.add_order(o)
    o_rank = o.rank
    assert (o.rank is not None)
    ob.remove_shares_from_order(o, D(11))
    assert (o.rank == o_rank)
    assert (o.num_shares == D(89))
    assert (o in ob.get_by_instrument_id("i").get_bids())
    with pytest.raises(ValueError):
        ob.remove_shares_from_order(o, D(100))
    ob.remove_shares_from_order(o, D(89))
    assert (o.rank == o_rank)
    assert (o not in ob.get_by_account_id("u").bids)
    assert (not ob.get_by_instrument_id("i").get_bids())


def test_cross():
    ob = OrderBook()
    o0 = Order("u", Order.bid, "i", D(30), D(7))
    o1 = Order("u", Order.bid, "i", D(31), D(6))
    o2 = Order("u", Order.bid, "i", D(31), D(8))
    o3 = Order("u", Order.bid, "i", D(30), D(8))
    o4 = Order("u", Order.bid, "i", D(29), D(8))
    o_match = Order("u2", Order.ask, "i", D(29), D(34))
    orders = [o0, o1, o2, o3, o4, o_match]
    for i in orders:
        ob.add_order(i)
    assert (ob.get_by_instrument_id("i").get_best_bid() == D(31))
    assert (ob.get_by_instrument_id("i").get_best_ask() == D(29))
    exchanges = []
    while True:
        cross = ob.get_priority_cross("i")
        if not cross:
            break
        shares = min(cross["post"].num_shares, cross["match"].num_shares)
        exchanges.append(shares)
        assert (shares > D(0))
        ob.remove_shares_from_order(cross["post"], shares)
        ob.remove_shares_from_order(cross["match"], shares)
    assert (exchanges == [6, 8, 7, 8, 5])
    assert (o_match.num_shares == 0)
    assert (o4.num_shares == 3)


# Dumping and constructing objects.

def test_order_dump_and_construct():
    o = Order("u", Order.bid, "i", D(2), D(11))
    o2 = Order(*o.dump())
    assert (str(o) == str(o2) and o.dump() == o2.dump())
    ob = OrderBook()
    ob.add_order(o)
    o2 = Order(*o.dump())
    assert (str(o) == str(o2) and o.dump() == o2.dump())
