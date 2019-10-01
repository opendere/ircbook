# Copyright (c) 2016 the IrcBook team
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

from decimal import Decimal as D

from trading.instruments import Instruments, Instrument
from trading.orderbook import OrderBook, Order
from trading.positions import Positions
from trading.tradingengine import TradingEngine, Trades

trades = Trades()
ob = OrderBook()
positions = Positions()
engine = TradingEngine(ob, positions, trades)

# create instrument
instruments = Instruments()
sanders_instr = Instrument(text="bernie sanders wins",
                           oracle_count_threshold=2,
                           oracles={"justan", "modulus"})

inst_id = instruments.add_instrument(sanders_instr)

# bids
e0 = engine.place(
    Order(account_id="modulus", side=Order.bid, instrument_id=inst_id, price=D(22), num_shares=D(2))
)
e1 = engine.place(Order("modulus", Order.bid, inst_id, D(23), D(1)))
e2 = engine.place(Order("justan", Order.ask, inst_id, D(24), D(4)))
# the order book for instrument inst_id (sanders_instr id) is
# buys: 2 for 22, 1 for 23
# sells: 4 at 24

# add an order that crosses the best bid:
e3 = engine.place(Order("justan", Order.ask, inst_id, D(21), D(2)))

print(e0)
print(e1)
print(e2)
print(e3)

while True:
    cross = ob.get_priority_cross(inst_id)
    if not cross:
        break

    print("a partial trade execution occurred:")
    print("posted price: " + str(cross["post"].price))
    print("crossed price: " + str(cross["match"].price))
    print(str(cross["post"]) + "\n" + str(cross["match"]))

    # print(str(engine.settle_cross(**cross)))

print()
justan_portfolio = positions.get_portfolio("justan")
print("justan: ")
print("cash: " + str(justan_portfolio.get_cash_balance()))
for coupon in justan_portfolio.get_coupons().values():
    print("inst_id: " + str(coupon.instrument_id))
    print("shares: " + str(coupon.get_num_shares()) + " " + str(coupon.side))
    print(str(coupon))

modulus_portfolio = positions.get_portfolio("modulus")
print("modulus: ")
print("cash: " + str(modulus_portfolio.get_cash_balance()))
for coupon in modulus_portfolio.get_coupons().values():
    print("inst_id: " + str(coupon.instrument_id))
    print("shares: " + str(coupon.get_num_shares()) + " " + str(coupon.side))
    print(str(coupon))

# figure out whether an order can be added
justan_shares_dict = justan_portfolio.get_shares_dict()
justan_orders = ob.get_by_account_id("justan")
print(justan_shares_dict)

print("justans order-fill-liabilities:")
print(justan_orders.get_additional_liability(justan_shares_dict))

# attempt order
attempted_order = Order("justan", Order.bid, inst_id, D(50), D(1000000))
ob.add_order(attempted_order)

print("justans order-fill-liabilities with new order:")
justan_new_shares_dict = justan_portfolio.get_shares_dict()
print(justan_orders.get_additional_liability(justan_new_shares_dict))

fill_cash = justan_portfolio.get_cash_balance()
fill_cash -= justan_orders.get_additional_liability(justan_new_shares_dict)
if fill_cash < 0:
    ob.remove_order(attempted_order)

print("justans order-fill-liabilities:")
justan_new_shares_dict = justan_portfolio.get_shares_dict()
print(justan_orders.get_additional_liability(justan_new_shares_dict))

print("last 1 trades for instrument" + str(inst_id))
print(engine.get_trades().get_most_recent(1)[0])
