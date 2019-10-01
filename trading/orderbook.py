# Copyright (c) 2016 the IrcBook team
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

from collections import defaultdict
from datetime import datetime
from decimal import Decimal as D

from sortedcontainers import SortedList


# Sorting rules.
def opricerank(o):
    return o.price, -o.rank


def antiopricerank(o):
    return D(100) - o.price, -o.rank


def orisk(o):
    if o.side == Order.bid:
        return -o.price
    elif o.side == Order.ask:
        return o.price


class OrderBook:
    """
    Representation of all open orders across all instruments.
    """

    def __init__(self, book=None):
        """
        Consumes orders, a list of Order objects to load
        orders to mapping by instrument_id and mapping by account_id
        """
        if book is None:
            book = {}
        self.orders_by_acct = defaultdict(AccountOrders)
        self.orders_by_instrument = defaultdict(InstrumentOrders)

        if book:
            for order in book["orders"]:
                self.add_order(Order(*order))
            for i in book["rank"]:
                self.orders_by_instrument[i].next_order_rank = book["rank"][i] + 1

    def get_by_account_id(self, account_id):
        """
        Consumes an account object,
        returns a set of open orders belonging to account for all instruments
        """
        if account_id in self.orders_by_acct:
            return self.orders_by_acct[account_id]
        return None

    def get_by_instrument_id(self, instrument_id):
        """
        Consumes an instrument_id,
        returns an InstrumentOrders object for said instrument
        """
        if instrument_id in self.orders_by_instrument:
            return self.orders_by_instrument[instrument_id]
        return None

    def add_order(self, order):
        """
        Consumes an Order object,
        adds the order to the order_by_instrument map and orders_by_acct map
        """
        self.orders_by_acct[order.account_id].add(order)
        self.orders_by_instrument[order.instrument_id].add(order)

    def remove_order(self, order):
        self.orders_by_acct[order.account_id].remove(order)
        self.orders_by_instrument[order.instrument_id].remove(order)

    def remove_shares_from_order(self, order, removed_num_shares):
        new_num_shares = order.num_shares - removed_num_shares
        if new_num_shares < D(0):
            raise ValueError("Can't remove more shares than exist.")
        self.remove_order(order)
        order.num_shares = new_num_shares
        if order.num_shares > D(0):
            self.add_order(order)

    def get_priority_cross(self, instrument_id):
        """
        Consumes an instrument_id
        Returns the crossed order-pair that should first be matched
        for the given instrument. Simulates addition of orders and
        finds first cross that happened. This is allows multiple
        orders to be added before officially being settled
        """
        orders = self.get_by_instrument_id(instrument_id)
        if not orders:
            return None
        bids, asks = orders.get_bids(), orders.get_asks()
        if not bids or not asks:
            return None
        if orders.get_best_bid() < orders.get_best_ask():
            return None
        obid = bids[-1]
        oask = asks[-1]
        if obid.rank < oask.rank:
            return {"post": obid, "match": oask}
        elif obid.rank > oask.rank:
            return {"match": obid, "post": oask}
        else:
            raise ValueError("Two orders on same instrument cannot have equal rank: ", str(oask), str(obid))

    def dump(self):
        l = []
        ranks = {}
        for i in self.orders_by_instrument.values():
            for j in i.bids:
                if j.instrument_id not in ranks:
                    ranks[j.instrument_id] = j.rank
                else:
                    ranks[j.instrument_id] = max(ranks[j.instrument_id], j.rank)
                l.append(j.dump())
            for j in i.asks:
                if j.instrument_id not in ranks:
                    ranks[j.instrument_id] = j.rank
                else:
                    ranks[j.instrument_id] = max(ranks[j.instrument_id], j.rank)
                l.append(j.dump())
        return {"rank": ranks, "orders": l}


class AccountOrders:
    def __init__(self):
        self.bids = set()
        self.asks = set()
        # map of instrument_ids to liability calculators
        self.risk = Risk()

    def add(self, order):
        if order.side == Order.bid:
            self.bids.add(order)
        else:
            self.asks.add(order)

        self.risk.add(order)

    def remove(self, order):
        if order.side == Order.bid:
            self.bids.remove(order)
        else:
            self.asks.remove(order)

        self.risk.remove(order)

    def get_risk(self, inst):
        """Get us the risk for an instrument for this user."""
        return self.risk.get_risk(inst)

    def __getitem__(self, index):
        l = list(self.bids) + list(self.asks)
        if index < len(l):
            return l[index]
        raise IndexError("Index out of bounds: %d, size is %d" % (index, len(l)))

    def __len__(self):
        return len(self.bids) + len(self.asks)


class Risk:
    """Calculation of risk according to orders logged."""

    def __init__(self):
        self.risk = {}

    def add(self, order):
        """Add Order cost to the risk structure."""
        inst, side = order.instrument_id, order.side
        if inst in self.risk:
            if side in self.risk[inst]:
                self.risk[inst][side] += order.cost()
            else:
                self.risk[inst][side] = order.cost()
        else:
            self.risk[inst] = {side: order.cost()}

    def remove(self, order):
        """Remove an order from risk structure."""
        inst, side = order.instrument_id, order.side
        if self.risk[inst][side] < order.cost():
            raise ValueError("Attempting to remove more risk than exists.")
        self.risk[inst][side] -= order.cost()

    def get_risk(self, inst):
        """Returns risk state for a given claim."""
        result = {Order.bid: D(0), Order.ask: D(0)}
        if inst not in self.risk:
            return result
        if Order.ask in self.risk[inst]:
            result[Order.ask] = self.risk[inst][Order.ask]
        if Order.bid in self.risk[inst]:
            result[Order.bid] = self.risk[inst][Order.bid]
        return result


class InstrumentOrders:
    """
    Data structure maintaining sorted bids and asks for an instrument.
    """

    def __init__(self, next_order_rank=0):
        # lists ordered by posted value and secondarily by time entered
        self.bids = SortedList(key=opricerank)
        self.asks = SortedList(key=antiopricerank)

        # order in which an order was added, 1st, 2nd, ...
        self.next_order_rank = next_order_rank

    def get_asks(self):
        if self.asks:
            return self.asks
        return None

    def get_best_ask(self):
        if self.asks:
            return self.asks[-1].price
        return None

    def get_bids(self):
        if self.bids:
            return self.bids
        return None

    def get_best_bid(self):
        if self.bids:
            return self.bids[-1].price
        return None

    def add(self, order):
        if order.rank is None:
            order.rank = self.next_order_rank
            self.next_order_rank += 1

        if order.side == Order.bid:
            self.bids.add(order)
        else:
            self.asks.add(order)

    def remove(self, order):
        if order.side == Order.bid:
            self.bids.remove(order)
        else:
            self.asks.remove(order)


class Order:
    ask = "a"
    bid = "b"

    def __init__(self, account_id, side, instrument_id, price, num_shares, timestamp=None, rank=None):
        self.account_id = account_id
        self.side = side
        self.instrument_id = instrument_id
        self.price = D(price)
        self.num_shares = D(num_shares)
        if not timestamp:
            self.timestamp = datetime.utcnow()
        else:
            self.timestamp = datetime(*timestamp)
        self.rank = rank

        self._check_order_validity()

    def _check_order_validity(self):
        if not isinstance(self.account_id, str):
            raise ValueError("Account ID must be a string.")
        if self.side != Order.bid and self.side != Order.ask:
            raise ValueError("Invalid order side.")
        if not isinstance(self.instrument_id, str):
            raise ValueError("Instrument ID must be a string.")
        if self.price <= D(0) or self.price >= D(100) or not isinstance(self.price, D):
            raise ValueError("Price must be a Decimal higher than 0 and lower than 100.")
        if self.num_shares <= D(0) or not isinstance(self.num_shares, D):
            raise ValueError("Number of shares must be a positive Decimal.")
        if self.rank and self.rank < 0:
            raise ValueError("Rank must be zero or greater.")

    def get_buy_cost(self):
        return self.price * self.num_shares

    def set_rank(self, rank):
        self.rank = rank

    def __str__(self):
        return (str(self.instrument_id) + "#" + str(self.rank) + ": " +
                str(self.side) + " @ " + str(self.price) + " * " + str(self.num_shares))

    def name(self):
        return str(self.instrument_id) + '#' + str(self.rank)

    def matches(self, o):
        """Tell us whether an order would match another."""
        if self.account_id != o.account_id or self.instrument_id != o.instrument_id or self.side == o.side:
            return False
        if self.price == o.price:
            return True
        if self.side == Order.bid:
            return self.price > o.price
        elif self.side == Order.ask:
            return self.price < o.price

    def dump(self):
        return (self.account_id, self.side, self.instrument_id, str(self.price),
                str(self.num_shares), (self.timestamp.year, self.timestamp.month,
                                       self.timestamp.day, self.timestamp.hour, self.timestamp.minute,
                                       self.timestamp.second, self.timestamp.microsecond), self.rank)

    def cost(self):
        """Got sick of having this code all over the place."""
        if self.side == Order.bid:
            return self.price * self.num_shares
        elif self.side == Order.ask:
            return (D(100) - self.price) * self.num_shares
        else:
            raise ValueError("Invalid order side: {0}".format(self.side))
