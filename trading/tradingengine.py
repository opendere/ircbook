# Copyright (c) 2016 the IrcBook team
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

from collections import defaultdict
from datetime import datetime
from decimal import Decimal as D

from sortedcontainers import SortedList

from trading.orderbook import Order
from trading.positions import Coupon


class TradingEngine:
    """
    Interface between front end requests and orderbook/account models.
    """

    def __init__(self, orderbook, positions, trades):
        self.orderbook = orderbook
        self.positions = positions
        self.trades = trades

    def settle_cross(self, post, match):
        """
        Consumes post, the Order object with the price at which
        the trade will be settled and match, the Order object
        on the other side of the trade.

        Updates the orderbook by removing one of the orders
        and updating the other order with the remaining unmatched
        shares, or if they have equal num_shares, remove both.
        Update the positions.
        """
        instrument_id = post.instrument_id

        shares_exchanged = min(post.num_shares, match.num_shares)
        assert (shares_exchanged > D(0))
        if post.side == Order.bid:
            post_cost = post.price
        else:
            post_cost = D(100) - post.price

        match_cost = D(100) - post_cost

        # update positions
        post_side = (Coupon.yes if post.side == Order.bid else Coupon.no)
        post_coupon = Coupon(post.account_id, instrument_id, shares_exchanged, post_side)
        self.positions.add_coupon(post_coupon, post_cost)
        match_side = (Coupon.yes if match.side == Order.bid else Coupon.no)
        match_coupon = Coupon(match.account_id, instrument_id, shares_exchanged, match_side)
        self.positions.add_coupon(match_coupon, match_cost)

        # remove shares from order
        self.orderbook.remove_shares_from_order(post, shares_exchanged)
        self.orderbook.remove_shares_from_order(match, shares_exchanged)

        # Recalc risk:
        p_post = self.positions.get_portfolio(post.account_id)
        p_match = self.positions.get_portfolio(match.account_id)
        o_post = self.orderbook.get_by_account_id(p_post.account_id)
        o_match = self.orderbook.get_by_account_id(p_match.account_id)

        # store trade
        if post.side == Order.bid:
            trade = Trade(post.account_id, match.account_id, instrument_id, post.price, shares_exchanged)
        else:
            trade = Trade(match.account_id, post.account_id, instrument_id, post.price, shares_exchanged)

        self.trades.add_trade(trade)
        return trade

    def get_trades(self):
        return self.trades

    def place(self, order):
        """
        This function takes an order and places it on the book to the
        maximum possible extent. It will use as resources contrary orders,
        contrary coupons, and cash. It returns a dictionary containing all
        incidents related to the placement.
        """
        results = Placement()
        u = order.account_id
        p = self.positions.get_portfolio(u)
        if not p:
            self.positions.add_portfolio(u)
            p = self.positions.get_portfolio(u)
        inst = order.instrument_id
        cash_total = p.cash_balance
        coupon = p.get_coupon(inst)

        # First thing: are there contrary orders?

        inst_handler = self.orderbook.get_by_instrument_id(inst)
        account_handler = self.orderbook.get_by_account_id(u)
        if inst_handler:
            if order.side == Order.ask:
                inst_orders = inst_handler.get_bids()
            else:
                inst_orders = inst_handler.get_asks()
        else:
            inst_orders = None
        matching_orders = []
        if inst_orders:
            for i in inst_orders:
                if i.matches(order):
                    matching_orders.append(i)

        # If so, cancel them out in reversed order.
        matching_orders.reverse()
        for i in matching_orders:
            if order.num_shares > D(0):
                if i.num_shares > order.num_shares:
                    net_shares = i.num_shares - order.num_shares
                    results.cancelled_shares += order.num_shares
                    results.remaining_shares = net_shares
                    old_locked_cash = p.get_locked_cash_for_order_risks(account_handler.risk.risk)
                    self.orderbook.remove_shares_from_order(i, order.num_shares)
                    new_locked_cash = p.get_locked_cash_for_order_risks(account_handler.risk.risk)
                    results.lock.append(old_locked_cash, new_locked_cash)
                    return results
                if i.num_shares == order.num_shares:
                    results.cancelled_shares += i.num_shares
                    old_locked_cash = p.get_locked_cash_for_order_risks(account_handler.risk.risk)
                    self.orderbook.remove_order(i)
                    new_locked_cash = p.get_locked_cash_for_order_risks(account_handler.risk.risk)
                    results.lock.append(old_locked_cash, new_locked_cash)
                    return results
                if i.num_shares < order.num_shares:
                    results.cancelled_shares += i.num_shares
                    order.num_shares -= i.num_shares
                    old_locked_cash = p.get_locked_cash_for_order_risks(account_handler.risk.risk)
                    self.orderbook.remove_order(i)
                    new_locked_cash = p.get_locked_cash_for_order_risks(account_handler.risk.risk)
                    results.lock.append(old_locked_cash, new_locked_cash)
            else:
                return results

        # Calculate affordability.
        shares = order.num_shares
        if account_handler:
            afford = p.afford(account_handler.risk.risk, order)
        else:
            afford = p.afford({}, order)
        if afford <= D(0):
            return results
        order.num_shares = min(afford, shares)

        # Add, lock, and execute.
        self.orderbook.add_order(order)
        while True:
            cross = self.orderbook.get_priority_cross(inst)
            if not cross:
                break
            results.trades.append(self.settle_cross(**cross))

        # Calculate outcomes.
        shares_exchanged = D(0)
        for i in results.trades:
            shares_exchanged += i.shares
        results.shares_exchanged = shares_exchanged
        results.cash = cash_total - p.cash_balance
        new_coupon = p.get_coupon(inst)
        if coupon:
            results.old_shares, results.old_side = coupon.shares, coupon.side
        if new_coupon:
            results.new_shares, results.new_side = new_coupon.shares, new_coupon.side
        results.residual = shares - shares_exchanged
        return results


def t_list():
    return SortedList(key=lambda t: t.timestamp)


class Trades:
    def __init__(self, l=None):
        if l is None:
            l = []
        self.sorted_trades = SortedList(key=lambda t: t.timestamp)
        self.trades_by_instrument = defaultdict(t_list)
        for i in l:
            self.add_trade(Trade(*i))

    def add_trade(self, trade):
        self.sorted_trades.add(trade)
        self.trades_by_instrument[trade.instrument_id].add(trade)

    def get_in_timerange(self, starttime, endtime, instrument_id=None):
        if instrument_id:
            trade_list = self.trades_by_instrument[instrument_id]
        else:
            trade_list = self.sorted_trades
        return trade_list.irange(trade_list.bisect(starttime), trade_list.bisect(endtime))

    def get_most_recent(self, n, instrument_id=None):
        if instrument_id:
            return self.trades_by_instrument[instrument_id][-n:]
        else:
            return self.sorted_trades[-n:]

    def dump(self):
        l = []
        for i in self.sorted_trades:
            l.append(i.dump())
        return l


class Trade:
    def __init__(self, sell_user, buy_user, instrument_id, price, shares, timestamp=None):

        self.sell_user = sell_user
        self.buy_user = buy_user
        self.instrument_id = instrument_id
        self.price = D(price)
        self.shares = D(shares)
        if not timestamp:
            self.timestamp = datetime.utcnow()
        else:
            self.timestamp = datetime(*timestamp)

    def __str__(self):
        return (str(self.timestamp) + ": " + self.sell_user + " -> " +
                self.buy_user + " @ " + str(self.price) + " * " + str(self.shares))

    def dump(self):
        return (self.sell_user, self.buy_user, self.instrument_id, str(self.price),
                str(self.shares), (self.timestamp.year, self.timestamp.month,
                                   self.timestamp.day, self.timestamp.hour, self.timestamp.minute,
                                   self.timestamp.second, self.timestamp.microsecond))


class Placement:
    """This object represents the results of trading."""

    def __init__(self):
        self.cash = D(0)
        self.cancelled_shares = D(0)
        self.trades = []
        self.shares_exchanged = D(0)
        self.remaining_shares = D(0)
        self.old_shares = D(0)
        self.old_side = None
        self.new_shares = D(0)
        self.new_side = None
        self.invalid = D(0)
        self.lock = []
        self.residual = D(0)

    def __str__(self):
        s = ""
        if self.cancelled_shares > D(0):
            s += "Orders for {0} coupons cancelled. ".format(self.cancelled_shares)
        s += "{0} coupons traded. ".format(self.shares_exchanged)
        if self.trades:
            s += "{0} orders matched. ".format(len(self.trades))
        if self.remaining_shares > D(0):
            s += "Orders for {0} coupons remain queued. ".format(self.remaining_shares)
        if self.invalid > D(0):
            s += "Orders for {0} coupons were not booked. ".format(self.invalid_shares)
        if self.cash > D(0):
            s += "Total cost of order: {0}. ".format(self.cash)
        elif self.cash < D(0):
            s += "Total revenue from order: {0}. ".format(abs(self.cash))
        return s.strip()
