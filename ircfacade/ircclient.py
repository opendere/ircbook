import re

import irc.client

from ircfacade.commands import InvalidCommand


class IrcConnection:
    def __init__(self, reactor, connection_parameters, shutdown_handler, network, commands):
        self.config = connection_parameters
        self.commands = commands
        self.c = None
        self.r = reactor
        self.shutdownHandler = shutdown_handler
        self.network = network

    def try_connect(self, max_attempts=10):
        """Takes a reactor object and attempts to connect 10 times."""
        connected, attempts = False, 0
        while not connected:
            try:
                print("Connection attempt: " + str(attempts))
                c = self.connect_to_server()
                print("Connected: from Main.")
                connected = True
            except irc.client.ServerConnectionError:
                print("Connection failed.")
                attempts += 1
            if attempts > max_attempts:
                raise SystemExit("Impossible to connect after " + str(max_attempts) + " attempts.")
        self.c = c
        return c

    def connect_to_server(self):
        server = self.config.server()
        port = self.config.port()
        nick = self.config.nick()
        c = self.r.server().connect(server, port, nick)
        return c

    def respond(self, e, m):
        """Respond with message m to the sender of event or a channel e through connection c."""
        # If string is too long, split it.
        m = str(m)
        result = [m]
        if len(m.encode("latin1")) >= 450:
            s = m.split(" ")
            size_in_bytes = 0
            cut_point = 0
            result = []
            for i in range(len(s)):
                if size_in_bytes + len(s[i].encode("latin1")) + 1 >= 450:
                    result.append(" ".join(s[cut_point:i]))
                    cut_point = i
                    size_in_bytes = 0
                else:
                    size_in_bytes += len(s[i]) + 1
            result.append(" ".join(s[cut_point:]))
        for i in result:
            if e.target in self.config.active_channels:
                self.c.privmsg(e.target, i)
            else:
                self.c.privmsg(e.source.nick, i)

    def join(self, channel):
        print("Joining channel: " + channel)
        self.c.join(channel)

    def response_callback(self, event):
        def response_func(message):
            self.respond(event, message)

        return response_func

    def on_pm(self, c, e):
        try:
            command = self.commands.prepare(e.arguments[0])
            callback = self.response_callback(e)
            self.commands.execute(command, e, callback)
        except InvalidCommand as ex:
            self.respond(e, str(ex))
        except ValueError as ex:
            self.respond(e, str(ex))

    def on_disconnect(self, c, e):
        print("Connection lost. " + str(e))
        print("Attempting to reconnect...")
        self.try_connect()

    def stop(self):
        """Disconnects bot and saves state. Owner command."""
        self.c.remove_global_handler("disconnect", self.on_disconnect)
        self.c.disconnect("Quit!")
        self.shutdownHandler()
        raise SystemExit("Terminated by owner.")

    @staticmethod
    def is_command(sentence):
        if len(sentence) < 1:
            return False
        return re.search(r'^\$\D\S*', sentence[0])

    def on_chan(self, c, e):
        """Respond to channel commands."""
        if not self.config.has_active_channel(e.target):
            return
        if not self.is_command(e.arguments):
            return
        try:
            command = self.commands.prepare(e.arguments[0])
            self.commands.execute(command, e, self.response_callback(e))
        except InvalidCommand as ex:
            e.target = "IrcBook"
            self.respond(e, str(ex))
        except ValueError as eve:
            e.target = "IrcBook"
            self.respond(e, str(eve))

    @staticmethod
    def on_connect(c, e):
        print("Connection realised, on_connect.")

    def on_notice(self, c, e):
        print("Notice: " + str(c) + ", " + str(e))
        auth_service = self.network.get_auth_service()
        if auth_service.is_auth_request(e.source, e.arguments[0]):
            c.privmsg("nickserv", "identify " + self.config.password())
            print("Authenticating.")
        if auth_service.is_auth_confirmation(e.source, e.arguments[0]):
            print("Auth succeeded, now joining channels.")
            self.join_channels(c)
            print("Ready.")

    def join_channels(self, c):
        c.join(self.config.log_chan())
        for ch in self.config.channels:
            c.join(ch)

    def register_handlers(self):
        self.c.add_global_handler("welcome", self.on_connect)
        self.c.add_global_handler("disconnect", self.on_disconnect)
        self.c.add_global_handler("privnotice", self.on_notice)
        self.c.add_global_handler("privmsg", self.on_pm)
        self.c.add_global_handler("pubmsg", self.on_chan)


class IrcClient:
    def __init__(self, config, network):
        self.connection = None
        self.config = config
        self.network = network

    def run(self, commands, shutdown_handler):
        reactor = irc.client.Reactor()
        irc.client.ServerConnection.buffer_class.encoding = 'latin-1'
        connection = IrcConnection(reactor, self.config, shutdown_handler, self.network, commands)
        connection.try_connect()
        connection.register_handlers()
        self.connection = connection
        reactor.process_forever()

    def stop(self):
        self.connection.stop()

    def join(self, channel):
        self.connection.join(channel)
