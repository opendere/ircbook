# Copyright (c) 2016 the IrcBook team
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

from collections import defaultdict
from decimal import Decimal as D


class Positions:
    """
    position of all accounts.
    """

    def __init__(self, pos=None):

        # map of users to their portfolios
        if pos is None:
            pos = []
        self.portfolios = defaultdict(Portfolio)

        for i in pos:
            self.portfolios[i[0]] = Portfolio(*i)

    def add_coupon(self, coupon, cost=D(0)):
        if coupon.account_id not in self.portfolios:
            self.portfolios[coupon.account_id] = Portfolio(coupon.account_id)
        self.portfolios[coupon.account_id].add_coupon(coupon, cost)

    def get_coupons(self, account_id):
        return self.portfolios[account_id].get_coupons()

    def get_portfolio(self, account_id):
        if account_id in self.portfolios:
            return self.portfolios[account_id]
        else:
            return None

    def add_portfolio(self, account_id):
        self.portfolios[account_id] = Portfolio(account_id)

    def dump(self):
        l = []
        for i in self.portfolios.values():
            l.append(i.dump())
        return l

    def __eq__(self, o):
        return isinstance(o, Positions) and self.__dict__ == o.__dict__

    def __ne__(self, o):
        return not self == o


class Portfolio:
    """
    portfolio of a single account.
    """

    def __init__(self, account_id, coupons=None, cash_balance=D(1000000)):
        if coupons is None:
            coupons = []
        self.account_id = account_id
        self.coupons = {}
        if D(cash_balance) < D(0):
            raise ValueError("Cash must be a non-negative Decimal.")
        self.cash_balance = D(cash_balance)

        for coupon in coupons:
            c = Coupon(*coupon)
            self.coupons[c.instrument_id] = c

    def get_unlocked_cash(self, order_risks):
        return self.cash_balance - self.get_locked_cash_for_order_risks(order_risks)

    def get_coupon(self, instrument_id):
        if instrument_id in self.coupons:
            return self.coupons[instrument_id]
        else:
            return None

    def get_coupons(self):
        return self.coupons

    def get_shares_dict(self):
        """
        return mapping of instrument_id to share count where share count
        is positive for yes coupons and negative for no coupons
        """
        shares_dict = {}
        for instrument_id, coupon in self.coupons.items():
            num_shares = coupon.shares * (1 if coupon.side == Coupon.yes else -1)
            shares_dict[instrument_id] = num_shares
        return shares_dict

    def get_cash_balance(self):
        return self.cash_balance

    def add_coupon(self, new_coupon, cost=D(0)):

        if not isinstance(new_coupon, Coupon):
            new_coupon = Coupon(*new_coupon)
        # Check if it's ours.
        if self.account_id != new_coupon.account_id:
            raise ValueError("Cannot add someone else's coupon.")

        # if new coupon, simply add the coupon
        if new_coupon.instrument_id not in self.coupons:
            self.coupons[new_coupon.instrument_id] = new_coupon
            self.cash_balance -= cost * new_coupon.shares

        # else, update cash and then the number of shares
        else:
            curr_coupon = self.coupons[new_coupon.instrument_id]
            if curr_coupon.side == new_coupon.side:
                self.cash_balance -= cost * new_coupon.shares

            # else, you are hedging/closing
            else:
                # if you hedge, but don't flip from net yes to net no or vice versa,
                if curr_coupon.shares >= new_coupon.shares:
                    self.cash_balance += (D(100) - cost) * new_coupon.shares

                    # else, you have hedged your position for curr_coupon shares, you earn
                    # 100 for each hedge and you lose the cost for each new_coupon
                else:
                    self.cash_balance += D(100) * curr_coupon.shares
                    self.cash_balance -= cost * new_coupon.shares

            self.coupons[new_coupon.instrument_id].add_shares(new_coupon.side, new_coupon.shares)

        # if coupon has 0 shares, remove it
        if self.coupons[new_coupon.instrument_id].get_num_shares() == D(0):
            del self.coupons[new_coupon.instrument_id]

    def get_locked_cash_for_order_risks(self, order_risks):
        """
        determine the locked_cash based on
        - positions in portfolio and
        - risks from orders

        this function replaces self.locked_cash
        """
        locked_cash = D(0)
        for inst in order_risks:
            c = self.get_coupon(inst)
            r = order_risks[inst]
            a, b = D(0), D(0)
            if "a" in r:
                a = r["a"]
            if "b" in r:
                b = r["b"]
            if c:
                if c.side == Coupon.yes:
                    a -= D(100) * c.shares
                elif c.side == Coupon.no:
                    b -= D(100) * c.shares
            locked_cash += max(a, b)
        return locked_cash

    def afford(self, risk, order):
        locking = D(0)
        for inst in risk:
            if inst != order.instrument_id:
                c = self.get_coupon(inst)
                r = risk[inst]
                a, b = D(0), D(0)
                if "a" in r:
                    a = r["a"]
                if "b" in r:
                    b = r["b"]
                if c:
                    if c.side == Coupon.yes:
                        a -= D(100) * c.shares
                    elif c.side == Coupon.no:
                        b -= D(100) * c.shares
                locking += max(a, b)
        available = self.cash_balance - locking
        a, b = D(0), D(0)
        if order.instrument_id in risk:
            if "a" in risk[order.instrument_id]:
                a = risk[order.instrument_id]["a"]
            if "b" in risk[order.instrument_id]:
                b = risk[order.instrument_id]["b"]
        c = self.get_coupon(order.instrument_id)
        if c:
            if c.side == Coupon.yes:
                a -= D(100) * c.shares
            elif c.side == Coupon.no:
                b -= D(100) * c.shares
        if order.side == "a":
            result = (available - a) // (D(100) - order.price)
        else:
            result = (available - b) // order.price
        return result

    def dump(self):
        coupons = []
        for i in self.coupons.values():
            coupons.append(i.dump())
        return self.account_id, coupons, str(self.cash_balance)

    def __eq__(self, o):
        return isinstance(o, Portfolio) and self.__dict__ == o.__dict__

    def __ne__(self, o):
        return not self == o


class Coupon:
    yes = "y"
    no = "n"

    def __init__(self, account_id, instrument_id, shares, side):
        if not isinstance(account_id, str):
            raise ValueError("Account ID must be a string.")
        self.account_id = account_id
        if not isinstance(instrument_id, str):
            raise ValueError("Instrument ID must be a string.")
        self.instrument_id = instrument_id
        if D(shares) <= D(0):
            raise ValueError("Shares must be a positive Decimal.")
        self.shares = D(shares)
        if side != Coupon.yes and side != Coupon.no:
            raise ValueError("Coupon side must be yes or no.")
        self.side = side

    def add_shares(self, side, num_shares):
        if self.side == side:
            self.shares += num_shares
        else:
            self.shares -= num_shares
            if self.shares < D(0):
                self.side = side
                self.shares = -self.shares

    def get_num_shares(self):
        return self.shares

    def matches(self, side):
        if self.side == Coupon.yes and side == "a":
            return True
        elif self.side == Coupon.no and side == "b":
            return True
        else:
            return False

    def __str__(self):
        s = self.instrument_id + ": " + self.side + " * " + str(self.shares)
        return s

    def dump(self):
        return self.account_id, self.instrument_id, str(self.shares), self.side

    def __eq__(self, o):
        return isinstance(o, Coupon) and self.__dict__ == o.__dict__

    def __ne__(self, o):
        return not self == o
