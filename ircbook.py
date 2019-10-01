# coding=latin-1
import fnmatch
import json
import re
from datetime import date
from decimal import Decimal as D
from decimal import InvalidOperation as DIO

from config import Configuration
# IrcBook: a prediction market for IRC.
from ircfacade import commands
from ircfacade.commands import Command, NoMatchingCommand
from ircfacade.ircclient import IrcClient
from ircfacade.networks import Networks
from trading.orderbook import OrderBook, Order
from trading.positions import Positions
from trading.tradingengine import TradingEngine, Trades
from util.dateutils import today, parse_iso_date
from util.stringutils import pretty_list

config = Configuration("conf")
network = Networks.get_freenode()
ircclient = IrcClient(config, network)


# Helper functions and data structures:

def dirty(func):
    def my_func(*args):
        func(*args)
        args[0].save()

    return my_func


class Users:
    """
    Represent user information.
    """

    def __init__(self, state=None):
        if state is None:
            state = {}
        self.users = {}
        if state:
            if state["Users"]:
                for i in state["Users"]:
                    u = User(*i)
                    self.users[u.name] = u
            if state["Positions"]:
                self.positions = Positions(state["Positions"])
            else:
                self.positions = Positions()
            if state["Orderbook"]:
                self.ob = OrderBook(state["Orderbook"])
            else:
                self.ob = OrderBook()
            if state["Trades"]:
                self.trades = Trades(state["Trades"])
            else:
                self.trades = Trades()
        else:
            self.positions = Positions()
            self.ob = OrderBook()
            self.trades = Trades()

    @dirty
    def add(self, user):
        if user.name in self.users:
            raise ValueError("User already registered.")
        else:
            self.users[user.name] = user
            self.positions.add_portfolio(user.name)

    def get_user(self, name):
        if name in self.users:
            return self.users[name]
        else:
            for i in self.users.values():
                if i.nick == name:
                    return i
            raise ValueError("User {0} does not exist.".format(name))

    def save(self):
        with open("status.txt", "w") as f:
            users = []
            for i in self.users.values():
                users.append(i.dump())
            ob = self.ob.dump()
            pos = self.positions.dump()
            trades = self.trades.dump()
            json.dump({"Users": users, "Orderbook": ob, "Positions": pos,
                       "Trades": trades}, f, indent=1)

    def __iter__(self):
        return iter(self.users.values())

    def __len__(self):
        return len(self.users)


class User:
    @staticmethod
    def save():
        users.save()

    def __init__(self, name, confirmed=False, bday=None, promoter=None, nick=None):
        self.name = name
        self.confirmed = confirmed
        if not bday:
            self.bday = today()
        else:
            self.bday = date(*bday)
        self.promoter = promoter
        self.nick = nick

    @dirty
    def confirm(self, by):
        if config.is_owner(by):
            if not self.confirmed:
                self.confirmed, self.promoter = True, by
            else:
                raise ValueError("User " + str(self.name) + " already confirmed by " + str(self.promoter))
        else:
            raise ValueError("Not authorised to confirm accounts.")

    def dump(self):
        return self.name, self.confirmed, (self.bday.year, self.bday.month, self.bday.day), self.promoter, self.nick


try:
    with open("status.txt", "r") as f:
        users = Users(state=json.load(f))
except FileNotFoundError:
    users = Users()


class Claims:
    def __init__(self, l=None):
        if l is None:
            l = []
        self.claims = {}
        for i in l:
            cl = Claim(*i)
            self.claims[cl.name] = cl

    @dirty
    def add(self, claim):
        if claim.name in self.claims:
            raise ValueError("Claim already exists.")
        elif (claim.expires - today()).days <= 0:
            raise ValueError("Expiration date must occur in the future.")
        else:
            self.claims[claim.name] = claim

    def save(self):
        with open("claims.txt", "w") as f:
            json.dump(self.dump(), f, indent=1)

    def get_claim(self, name):
        if name in self.claims:
            return self.claims[name]
        else:
            raise ValueError("Claim " + str(name) + " does not exist.")

    def dump(self):
        l = []
        for i in self.claims.values():
            l.append(i.dump())
        return l


class Claim:
    def __init__(self, name, expires, desc, creator, approved=None, result=None, bday=None):
        if isinstance(expires, date):
            self.expires = expires
        else:
            self.expires = date(*expires)
        if not bday and self.expired():
            raise ValueError("Expiration must occur in the future.")
        if not bday:
            self.bday = today()
        else:
            self.bday = date(*bday)
        self.name = name
        self.creator = creator
        self.desc = desc
        if approved is not None:
            self.approved = approved
        else:
            self.approved = False
        self.result = result

    def expired(self):
        if (self.expires - today()).days <= 0:
            return True
        else:
            return False

    @dirty
    def approve(self, owner):
        if is_owner(owner):
            self.approved = True
            self.promoter = owner
        else:
            raise ValueError("You may not approve claims.")

    @dirty
    def resolve(self, result):
        self.expires = today()
        self.result = result

    @staticmethod
    def save():
        claims.save()

    def __str__(self):
        s = self.name + ": (" + str(self.bday) + "--" + str(self.expires)
        s += ") - " + self.desc
        # if self.approved == True: s += " approved by " + self.promoter
        if self.expired():
            s += " EXPIRED"
        if self.result is not None:
            s += " " + str(self.result)
        return s

    def dump(self):
        return (self.name, (self.expires.year, self.expires.month, self.expires.day), self.desc,
                self.creator, self.approved, self.result, (self.bday.year,
                                                           self.bday.month, self.bday.day))


try:
    with open("claims.txt", "r") as f:
        claims = Claims(json.load(f))
except FileNotFoundError:
    claims = Claims()

engine = TradingEngine(users.ob, users.positions, users.trades)


def is_owner(user):
    print("is owner %s" % user)
    return config.is_owner(user)


def place_order(o):
    """Attempt to place an order. Returns info about placement."""
    results = engine.place(o)
    users.save()
    return results


def nick_from_mask(s):
    m = re.match(r"(\S*)!.*", s)
    return m.group(1)


def vmask(s):
    m = re.match(r".*@(\S*)", s)
    return m.group(1)


def split_order(s):
    """Attempt to decompose an order ID."""
    m = re.match(r"(^\S+)#(\d+)$", s)
    claim = m.group(1)
    order_id = int(m.group(2))
    return claim, order_id


def owner_check(func):
    """Make sure that a command is executed by a bot owner."""

    def check_it(s, e, respond):
        if is_owner(e.source):
            func(s, e, respond)
        else:
            e.target = "IrcBook"
            respond("You lack appropriate permission.")

    check_it.__doc__ = func.__doc__
    return check_it


def user_check(func):
    """Make sure the command is executed by a registered user."""

    def do_func(s, e, respond):
        try:
            u = users.get_user(vmask(e.source))
        except ValueError:
            e.target = "IrcBook"
            respond("You're not registered.")
        else:
            if not u.confirmed:
                e.target = "IrcBook"
                respond("Sorry, your account is not confirmed yet.")
            else:
                func(s, e, respond)

    do_func.__doc__ = func.__doc__
    return do_func


def quiet(func):
    """Decorator to suppress channel output for commands."""

    def do_quietly(s, e, respond):
        e.target = "IrcBook"
        func(s, e, respond)

    do_quietly.__doc__ = func.__doc__
    return do_quietly


@quiet
def do_reg(s, e, respond):
    """Registers a user. No arguments."""
    if s:
        raise ValueError("This command takes no arguments.")
    users.add(User(vmask(e.source)))
    respond("Registered " + str(nick_from_mask(e.source)) + " with mask " + str(vmask(e.source)))


commands.registry.reg("register", do_reg)


@quiet
@owner_check
def do_confirm(s, e, respond):
    """Confirms a user. Takes the host mask. Owner command."""
    if len(s) != 1:
        raise ValueError("You must provide the user name to confirm as a single argument.")
    else:
        our_user = users.get_user(s[0])
        our_user.confirm(e.source)
        respond(our_user.name + " confirmed by " + str(our_user.promoter))


commands.registry.reg("confirm", do_confirm)


def get_desc(s):
    r = ""
    if len(s) == 1:
        return s[0].strip()
    for i in s:
        r = r + i + " "
    return r.strip()


@user_check
def do_create(s, e, respond):
    """Create a claim. Name, date (yyyy-mm-dd), and description."""
    if len(s) < 3:
        raise ValueError("Insufficient parameters: name, date as yyyy-mm-dd, and description are required.")
    if s[0] in claims.claims:
        raise ValueError("Claim already exists.")
    claim_date = parse_iso_date(s[1])
    if not claim_date:
        raise ValueError("Expiration date must be given as yyyy-mm-dd.")
    claim_desc = get_desc(s[2:])
    claims.add(Claim(s[0], claim_date, claim_desc, vmask(e.source)))
    respond("Claim created.")


commands.registry.reg("create", do_create)


@quiet
@owner_check
def do_approve(s, e, respond):
    """Approve a claim. Claim symbol. Owner command."""
    if len(s) != 1:
        raise ValueError("This command requires one single parameter.")
    claim = claims.get_claim(s[0])
    if claim.approved:
        raise ValueError("Claim already approved.")
    claim.approve(e.source)
    respond("Claim approved.")


commands.registry.reg("approve", do_approve)


def do_cash(s, e, respond):
    """Cash and unlocked cash in parentheses. Takes a user or implicit self."""
    if len(s) > 1:
        raise ValueError(
            "Too many parameters. You may pass one parameter to check someone else's cash, or none to check your own.")
    if len(s) == 0:
        por = users.positions.get_portfolio(users.get_user(vmask(e.source)).name)
    else:
        por = users.positions.get_portfolio(users.get_user(s[0]).name)

    order_risks = users.ob.get_by_account_id(i).risk.risk
    respond("{0} ({1})".format(
        por.cash_balance,
        por.get_unlocked_cash(order_risks)
    ))


commands.registry.reg("cash", do_cash)


def do_claims(s, e, respond):
    """Available claims. Optional claim symbol for details."""
    if len(s) > 1:
        raise ValueError("Too many parameters.")
    if len(s) == 0:
        c_list = pretty_list(list(filter(lambda k: (not claims.claims[k].expired()) and claims.claims[k].approved,
                                         sorted(claims.claims.keys(), key=lambda k: claims.claims[k].expires))))
        if c_list == "":
            raise ValueError("No claims are open for trade.")
        else:
            respond(c_list)
    else:
        if s[0] in claims.claims:
            respond(claims.claims[s[0]])
        else:
            raise ValueError("No such claim.")


commands.registry.reg("claims", do_claims)


@quiet
@owner_check
def do_unapproved(s, e, respond):
    """Unapproved claims. Optional symbol and then it returns true/false. Owner command."""
    if len(s) > 1:
        raise ValueError("Too many parameters.")
    if len(s) == 1:
        try:
            respond(not claims.claims[s[0]].approved)
        except KeyError:
            respond("No such claim.")
    else:
        l = []
        for i in claims.claims.values():
            if not i.approved:
                l.append(i.name)
        if len(l) == 0:
            respond("No pending claims.")
        else:
            respond(pretty_list(l))


commands.registry.reg("unapproved", do_unapproved)


@quiet
@owner_check
def do_unconfirmed(s, e, respond):
    """Unconfirmed users. Optional user, then returns true/false. Owner command."""
    if len(s) > 1:
        raise ValueError("Too many parameters.")
    if len(s) == 1:
        if s[0] in users.users:
            respond(str(not users.get_user(s[0]).confirmed))
        else:
            respond("No such user.")
    else:
        u_list = []
        for i in users.users.values():
            if not i.confirmed:
                u_list.append(i.name)
        if len(u_list) == 0:
            respond("No unconfirmed users.")
        else:
            respond(pretty_list(u_list))


commands.registry.reg("unconfirmed", do_unconfirmed)


@owner_check
def do_judge(s, e, respond):
    """Judge a claim true or false. Claim and y/n. Owner command."""
    if len(s) != 2 or (s[-1] != "y" and s[-1] != "n"):
        raise ValueError("Must provide claim and \"y\" or \"n\".")
    if s[0] in claims.claims:
        cl = claims.claims[s[0]]
        if not cl.approved:
            raise ValueError("Cannot judge unapproved claim.")
        result = s[-1]
        o_handler = users.ob.get_by_instrument_id(cl.name)
        if o_handler:
            o_asks = o_handler.get_asks()
            if o_asks:
                for i in list(o_handler.get_asks()):
                    users.ob.remove_order(i)
            o_bids = o_handler.get_bids()
            if o_bids:
                for i in list(o_handler.get_bids()):
                    users.ob.remove_order(i)
        for i in users.positions.portfolios.values():
            if cl.name in i.coupons:
                j = i.coupons[cl.name]
                if j.side == result:
                    i.cash_balance += D(100) * j.shares
                del i.coupons[j.instrument_id]
        for i in users.users:
            account_handler = users.ob.get_by_account_id(i)
            p = users.positions.get_portfolio(i)
            if account_handler:
                p.calc_risk(account_handler.risk.risk)
        if s[-1] == "y":
            cl.resolve(True)
        else:
            cl.resolve(False)
        users.save()
        respond(str(cl))
    else:
        raise ValueError("No such claim.")


commands.registry.reg("judge", do_judge)


@user_check
def do_buy(s, e, respond):
    """Buy. Symbol, y/n, price, shares."""
    if len(s) != 4:
        raise ValueError("Must provide claim, y/n, price and amount.")
    u = vmask(e.source)
    if s[1] != "y" and s[1] != "n":
        raise ValueError("Type of coupon must be \"y\" or \"n\".")
    if s[1] == "y":
        t = Order.bid
    else:
        t = Order.ask
    if s[0] not in claims.claims:
        raise ValueError("That claim does not exist.")
    cla = claims.claims[s[0]]
    if cla.expired() or not cla.approved:
        raise ValueError("Claim not open for trade.")
    try:
        if t == Order.bid:
            price = D(s[2])
        else:
            price = D(100) - D(s[2])
    except DIO:
        raise ValueError("Must provide a decimal for the price.")
    if price < D(0) or price > D(100): raise ValueError("Price must be 0--100.")
    try:
        amount = D(s[3])
    except DIO:
        raise ValueError("Must provide a decimal for quantity.")
    if amount <= 0:
        raise ValueError("Amount must be positive.")
    o = Order(u, t, cla.name, price, amount)
    result = place_order(o)
    respond(str(result))


commands.registry.reg("buy", do_buy)


@user_check
def do_sell(s, e, respond):
    """Sell. Symbol, y/n, price, shares."""
    if len(s) < 4:
        raise ValueError("Must provide claim, y/n, price and amount.")
    if s[1] == "y":
        s[1] = "n"
    elif s[1] == "n":
        s[1] = "y"
    try:
        s[2] = D(100) - D(s[2])
    except DIO:
        raise ValueError("Must provide a decimal for price.")
    do_buy(s, e, respond)


commands.registry.reg("sell", do_sell)


@quiet
@owner_check
def do_enter(s, e, respond):
    """Join a channel. Channel name. Owner command."""
    if len(s) != 1:
        raise ValueError("You must pass the channel as a single parameter.")
    channel = str(s[0])
    print("Joining %s" % channel)
    try:
        ircclient.join(channel)
    except Exception as exc:
        commands.log_msg(str(exc))
        respond(str(exc))
    else:
        config.add_channel(channel)
        config.save()
        respond("Joining.")


commands.registry.reg("enter", do_enter)


@quiet
@owner_check
def do_loud(s, e, respond):
    """Activate bot in a channel. Takes a compulsory channel that must have been entered."""
    if len(s) != 1:
        raise ValueError("You must pass the channel as a single parameter.")
    if not config.has_channel(s[0]):
        raise ValueError("Channel not in join list. Use $enter?")
    else:
        config.add_active_channel(s[0])
        config.save()
        respond("Activated on {0}.".format(s[0]))


commands.registry.reg("loud", do_loud)


@quiet
@owner_check
def do_unloud(s, e, respond):
    """Deactivate bot in a channel. Takes a compulsory channel that must be active."""
    if len(s) != 1:
        raise ValueError("You must pass the channel as a single parameter.")
    if not config.has_active_channel(s[0]):
        raise ValueError("Channel not in active list.")
    else:
        config.remove_active_channel(s[0])
        config.save()
        respond("Deactivated on {0}.".format(s[0]))


commands.registry.reg("unloud", do_unloud)


def do_ticker(s, e, respond):
    """Show ticker. Compulsory claim symbol."""
    if len(s) != 1:
        raise ValueError("Must pass only a claim symbol.")
    if s[0] not in claims.claims:
        raise ValueError("No such claim.")
    cl = claims.claims[s[0]]
    if cl.expired():
        last_trades = users.trades.get_most_recent(1, cl.name)
        if len(last_trades) > 0:
            last_price = str(last_trades[0].price)
        else:
            raise ValueError("Claim expired without trading.")
        respond("Claim closed. Last price: " + str(last_price))
        return
    o = users.ob.get_by_instrument_id(cl.name)
    if o is None:
        raise ValueError("No trades entered yet.")
    else:
        bid = str(o.get_best_bid())
        ask = str(o.get_best_ask())
        last_trades = users.trades.get_most_recent(0, cl.name)
        if len(last_trades) > 0:
            last_price = last_trades[-1].price
            price, volume = [], []
            for i in last_trades:
                volume.append(i.shares)
                price.append(i.price)
            avg = sum(price) / len(price)
            j = D(0)
            for i in range(len(volume)):
                j += volume[i] * price[i]
            wavg = j / sum(volume)
            outstanding = D(0)
            for i in users.users:
                p = users.positions.get_portfolio(i)
                coupon = p.get_coupon(cl.name)
                if coupon and coupon.side == "y":
                    outstanding += coupon.shares
            q = D("0.01")
            respond(
                "Claim: " + cl.name + ". Highest bid: " + str(bid) + ", lowest ask: " + str(ask) +
                ", last price: " + str(last_price) + ", volume: " + str(sum(volume)) +
                ", average: " + str(avg.quantize(q)) + ", weighted: " + str(wavg.quantize(q)) +
                ", coupons: " + str(outstanding))
        else:
            respond("Claim: {0}. Highest bid: {1}, lowest ask: {2}.".format(cl.name, bid, ask))


commands.registry.reg("ticker", do_ticker)


@quiet
def do_help(s, e, respond):
    """Help. Optional command to show syntax or show command list."""
    if len(s) > 1:
        raise ValueError("Pass a single command or nothing to see the command list.")
    elif len(s) == 0:
        respond("Command list: " + pretty_list(list(commands.registry.handlers.keys())))
    else:
        matching_commands = commands.registry.find(s[0])
        if not matching_commands:
            respond("No such command: " + s[0])
        else:
            if len(matching_commands) == 1:
                try:
                    handler = commands.registry.lookup(Command(s[0], []))
                    respond(handler.__doc__)
                except NoMatchingCommand:
                    raise ValueError("Internal error: failed to look up command: " + str(s[0]))
            else:
                respond("Ambiguous prefix: " + pretty_list(matching_commands))


commands.registry.reg("help", do_help)


def do_coupons(s, e, respond):
    """Shows coupons. Optional user or implicit self."""
    if len(s) > 1:
        raise ValueError("Give a user as parameter, or none to see your own coupons.")
    if len(s) == 0:
        u = users.get_user(vmask(e.source))
    else:
        u = users.get_user(s[0])
    coupons = users.positions.get_coupons(u.name)
    if len(coupons) == 0:
        raise ValueError("No coupons.")
    else:
        respond(pretty_list(list(coupons.values())))


commands.registry.reg("coupons", do_coupons)


@user_check
def do_orders(s, e, respond):
    """Outstanding orders. No arguments."""
    if len(s) != 0:
        raise ValueError("No arguments allowed.")
    o_handler = users.ob.get_by_account_id(vmask(e.source))
    if not o_handler:
        raise ValueError("No orders available.")
    orders = []
    orders += o_handler.asks
    orders += o_handler.bids
    if len(orders) == 0:
        raise ValueError("No orders available.")
    o_str = []
    for i in orders:
        o_str.append(str(i))
    respond(pretty_list(o_str))


commands.registry.reg("orders", do_orders)


def do_depth(s, e, respond):
    """Shows how much money is required to move the price. Takes a claim."""
    if len(s) != 1:
        raise ValueError("Must pass a claim as a single argument.")
    # TODO: extract Claims.get_valid_claim() logic from here.
    if s[0] not in claims.claims:
        raise ValueError("Claim {0} does not exist.".format(s[0]))
    cl = claims.claims[s[0]]
    if cl.expired():
        raise ValueError("Claim {0} no longer open for trade.".format(cl.name))
    if not cl.approved:
        raise ValueError("Claim {0} has not been approved for trading.".format(cl.name))
    ohandler = users.ob.get_by_instrument_id(cl.name)
    if not ohandler:
        raise ValueError("Claim {0} has no outstanding orders.".format(cl.name))
    bid = ohandler.get_best_bid()
    ask = ohandler.get_best_ask()
    if not bid and not ask:
        raise ValueError("Claim {0} has no outstanding orders.".format(cl.name))
    bid_depth, ask_depth = D(0), D(0)
    if bid:
        for i in range(len(ohandler.get_bids()) - 1, -1, -1):
            if ohandler.get_bids()[i].price != bid:
                break
            bid_depth += ohandler.get_bids()[i].num_shares
    if ask:
        for i in range(len(ohandler.get_asks()) - 1, -1, -1):
            if ohandler.get_asks()[i].price != ask:
                break
            ask_depth += ohandler.get_asks()[i].num_shares
    if not bid:
        bid = D(0)
    if not ask:
        ask = D(0)
    respond(str(cl.name) + ": Bid depth: " + str(bid * bid_depth) + ". Ask depth: " + str(ask * ask_depth) + ".")


commands.registry.reg("depth", do_depth)


def do_top(s, e, respond):
    user_list = list(users)
    user_list.sort(key=lambda user: users.positions.get_portfolio(user.name).get_cash_balance())
    user_list.reverse()
    top5 = list(map(lambda user: user.nick + ":" + str(users.positions.get_portfolio(user.name).get_cash_balance()),
                    user_list[0:5]))
    respond("Top 5: " + pretty_list(top5))


commands.registry.reg("top", do_top)


@user_check
def do_cancelstar(s, e, respond):
    """Cancels matching orders. Takes a glob pattern as parameter"""
    if len(s) != 1:
        raise ValueError("Pass a single pattern as a parameter")
    try:
        regex = re.compile(fnmatch.translate(s[0]))
    except:
        raise ValueError("Incorrect format of order ID, not a valid glob pattern")
    p = users.positions.get_portfolio(vmask(e.source))
    a_h = users.ob.get_by_account_id(p.account_id)
    orders = list(filter(lambda o: regex.match(o.name()), a_h))
    #    for order in a_h:
    for order in orders:
        if regex.match(order.name()):
            print("%s matches %s" % (regex, order.name()))
    print("matching %s orders" % (len(orders)))

    cancelled = 0
    cancelled_shares = 0
    for order in orders:
        if order.account_id == p.account_id:
            users.ob.remove_order(order)
            cancelled = cancelled + 1
            cancelled_shares = cancelled_shares + order.num_shares
    l1, l2 = p.calc_risk(a_h.risk.risk)
    users.save()
    respond("Cancelled {0} orders ({1} shares. {2} cash released)".format(cancelled, cancelled_shares, l1 - l2))


commands.registry.reg("gcancel", do_cancelstar)


@user_check
def do_cancel(s, e, respond):
    """Cancels an order. Takes an order ID in the form claim#id as a single parameter.."""
    if len(s) != 1:
        raise ValueError("Pass a single order ID as a parameter in the form claim#id.")
    try:
        cl, id = split_order(s[0])
    except:
        raise ValueError("Incorrect format of order ID. Try claim#id as shown by the orders command.")
    p = users.positions.get_portfolio(vmask(e.source))
    a_h = users.ob.get_by_account_id(p.account_id)
    if not a_h:
        raise ValueError("No such order.")
    risk = a_h.risk.risk
    c_h = users.ob.get_by_instrument_id(cl)
    if not c_h:
        raise ValueError("No such order.")
    bid, ask = None, None
    for i in c_h.bids:
        if i.rank == id:
            bid = i
    for i in c_h.asks:
        if i.rank == id:
            ask = i
    if (not ask) and (not bid):
        raise ValueError("No such order.")
    if ask and bid:
        raise ValueError("Two orders share this rank. Inconsistent state.")
    o = bid if bid else ask
    if o.account_id != p.account_id:
        raise ValueError("Cannot cancel someone else's order.")
    users.ob.remove_order(o)
    l1, l2 = p.calc_risk(risk)
    users.save()
    respond("Cancelled {0}, {1} coupons at {2} price. {3} cash released.".format(cl + "#" + str(id), o.num_shares,
                                                                                 o.price, l1 - l2))


commands.registry.reg("cancel", do_cancel)


@owner_check
def do_nick(s, e, respond):
    """Set a nick for a given user. Takes a host mask and a nick. Owner command."""
    if len(s) != 2:
        raise ValueError("Must pass host mask and nick as parameters.")
    mask, nick = s[0], s[1]
    if mask not in users.users:
        raise ValueError("No such user: {0}".format(mask))
    else:
        users.users[mask].nick = nick
        users.save()
        respond("Mask {0} assigned nick {1}.".format(mask, nick))


commands.registry.reg("nick", do_nick)


@quiet
@owner_check
def do_quit(s, e, respond):
    ircclient.stop()


commands.registry.reg("quit", do_quit)


def on_shutdown():
    users.save()
    claims.save()


def main():
    # Network initialisation.
    ircclient.run(commands, on_shutdown)


if __name__ == "__main__":
    main()
