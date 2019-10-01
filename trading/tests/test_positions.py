from decimal import InvalidOperation, Decimal as D

import pytest

from trading.positions import Positions, Portfolio, Coupon


def test_coupon_constructor():
    with pytest.raises(ValueError):
        c = Coupon(0, "i", D(1), Coupon.yes)
    with pytest.raises(ValueError):
        c = Coupon("u", 0, D(1), Coupon.yes)
    with pytest.raises(InvalidOperation):
        c = Coupon("u", "i", "fuck", Coupon.yes)
    with pytest.raises(ValueError):
        c = Coupon("u", "i", D(-1), Coupon.yes)
    with pytest.raises(ValueError):
        c = Coupon("u", "i", D(1), "u")


def test_coupon_equivalence():
    c = Coupon("u", "i", 2, Coupon.no)
    d = Coupon(*c.dump())
    assert (c == d and str(c) == str(d) and c.dump() == d.dump())


def test_portfolio():
    # Create a set of 10 coupons.
    l = []
    for i in range(10):
        c = Coupon("u", "i" + str(i), D(i + 1), Coupon.yes)
        l.append(c.dump())
    p = Portfolio("u", l, D(10), D(9))
    # Equivalence checks:
    p2 = Portfolio(*p.dump())
    dump1, dump2 = p.dump(), p2.dump()
    dump1[1].sort()
    dump2[1].sort()
    assert (dump1 == dump2)


def test_portfolio_checks_coupon_owner():
    p = Portfolio("u")
    c = Coupon("u2", "i", D(1), Coupon.yes)
    with pytest.raises(ValueError):
        p.add_coupon(c)


def test_positions():
    # Make a few portfolios with a few coupons each.
    portfolios = []
    for i in range(100):
        coupons = []
        for j in range(100):
            coupons.append(Coupon("u" + str(i), "i" + str(j), D(5), Coupon.yes).dump())
        portfolios.append(Portfolio("u" + str(i), coupons).dump())
    p = Positions(portfolios)
    p2 = Positions(p.dump())
    assert (p == p2)
