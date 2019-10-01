# This is meant to exercise the order logic.

from decimal import Decimal as D
from json import dumps
from random import randint as r

from trading.orderbook import OrderBook, Order
from trading.positions import Positions
from trading.tradingengine import TradingEngine, Trades

# Set this to true to get diagnostics.
DEBUG = True


def rc():
    """Give us a valid claim out of 10."""
    return r(1, 10)


def rp():
    """Give us a valid random price."""
    return D(r(47, 53))


def rq():
    """Give us a valid random amount."""
    return D(r(1, 10000))


ob = OrderBook()
pos = Positions()

users = []
for i in range(10):
    "Create 10 user portfolios."
    users.append("User " + str(i))
    pos.add_portfolio("User " + str(i))

trades = Trades()
engine = TradingEngine(ob, pos, trades)


def test_random_orders():
    """Try lots of orders and see if invariants are kept."""
    with open("results.txt", "w") as f:
        def dump(s, file):
            if DEBUG:
                file.write(str(s) + "\n")

        for i in range(1000):
            if DEBUG and i % 1000 == 0:
                print("Tick!")
            dump("Iteration: " + str(i), f)
            dump(dumps(ob.dump()), f)
            dump(dumps(pos.dump()), f)
            if r(0, 1) == 0:
                side = Order.bid
            else:
                side = Order.ask
            o = Order(users[r(0, 9)], side, "test", rp(), rq())
            dump(o, f)
            outcome = engine.place(o)
            if outcome.trades:
                for k in outcome.trades:
                    dump(k, f)
            dump(outcome, f)
            c = D(0)
            m = D(0)
            y = D(0)
            n = D(0)
            for j in users:
                p = pos.get_portfolio(j)
                dump("Cash: {0} ({1})".format(p.cash_balance, p.locked_cash), f)
                assert (p.cash_balance >= D(0))
                assert (p.locked_cash >= D(0))
                assert (p.cash_balance >= p.locked_cash)
                m += p.cash_balance
                if "test" in p.coupons:
                    coupon = p.coupons["test"]
                    c += coupon.shares
                    if coupon.side == "y":
                        y += coupon.shares
                        dump("Coupons y: " + str(coupon.shares), f)
                    elif coupon.side == "n":
                        n += coupon.shares
                        dump("Coupons n: " + str(coupon.shares), f)
                    else:
                        print("Error:", coupon.side)
            assert (c % 2 == 0)
            assert (m + ((c // D(2)) * D(100)) == D(10000000))
            assert (y == n)


# Setup.
ob2 = OrderBook()
pos2 = Positions()

users2 = []
for i in range(10):
    "Create 10 user portfolios."
    users2.append("User " + str(i))
    pos2.add_portfolio("User " + str(i))

trades2 = Trades()
engine2 = TradingEngine(ob2, pos2, trades2)


def test_random_multi():
    with open("results.txt", "a") as f:
        def dump(s, file):
            if DEBUG:
                file.write(str(s) + "\n")

        for i in range(1000):
            if DEBUG and i % 1000 == 0:
                print("Tick!")

            dump("Iteration: " + str(i), f)
            dump(dumps(ob2.dump()), f)
            dump(dumps(pos2.dump()), f)
            if r(0, 1) == 0:
                side = Order.bid
            else:
                side = Order.ask
            o = Order(users2[r(0, 9)], side, "Claim " + str(rc()), rp(), rq())
            dump(o, f)
            outcome = engine2.place(o)
            if outcome.trades:
                for k in outcome.trades:
                    dump(k, f)
            dump(outcome, f)
            c = D(0)
            m = D(0)
            y = D(0)
            n = D(0)
            for j in users2:
                p = pos2.get_portfolio(j)
                dump("Cash: {0} ({1})".format(p.cash_balance, p.locked_cash), f)
                assert (p.cash_balance >= D(0))
                assert (p.locked_cash >= D(0))
                assert (p.cash_balance >= p.locked_cash)
                m += p.cash_balance
                for coupon in p.coupons.values():
                    c += coupon.shares
                    if coupon.side == "y":
                        y += coupon.shares
                        dump("Coupons y: " + str(coupon.shares), f)
                    elif coupon.side == "n":
                        n += coupon.shares
                        dump("Coupons n: " + str(coupon.shares), f)
                    else:
                        print("Error:", coupon.side)
            assert (c % 2 == 0)
            assert (m + ((c // D(2)) * D(100)) == D(10000000))
            assert (y == n)
