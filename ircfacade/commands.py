# Out of a list, obtain the elements starting with a prefix.

from util.stringutils import pretty_list


class InvalidCommand(Exception):
    pass


class NoMatchingCommand(InvalidCommand):
    def __init__(self, message):
        super().__init__(message)


class InvalidCommandSyntax(InvalidCommand):
    def __init__(self, message):
        super().__init__(message)


class AmbiguousCommand(InvalidCommand):
    def __init__(self, message, commands):
        super().__init__(message)
        self.commands = commands


class Command:
    def __init__(self, command, args):
        self.command = command
        self.args = args

    def __repr__(self):
        if self.args:
            return "Command(" + self.command + " " + ' '.join(self.args) + ")"
        else:
            return "Command(" + self.command + ")"


class CommandRegistry:
    def __init__(self):
        self.handlers = {}

    def reg(self, s, func):
        self.handlers[s] = func

    def lookup(self, command):
        try:
            return self.handlers[command.command]
        except KeyError:
            raise NoMatchingCommand("Command not found: " + command.command)

    def find(self, p):
        matching_commands = []
        for i in self.handlers:
            if i.startswith(p):
                matching_commands.append(i)
        matching_commands.sort()
        return matching_commands


class CommandLine:
    def __init__(self, args):
        if not args:
            raise InvalidCommandSyntax("Missing command")
        if len(args[0]) == 0:
            raise InvalidCommandSyntax("Empty command")
        self.command = args[0][1:]
        self.args = args[1:]

    def __repr__(self):
        if self.args:
            return "CommandLine(" + self.command + " " + ' '.join(self.args) + ")"
        else:
            return "CommandLine(" + self.command + ")"


def log_msg(m):
    """Log to file."""
    with open("log.txt", "a") as f:
        f.write(str(m) + "\n")


def with_log(func):
    """Logging decorator."""

    def do_it(*a, **b):
        log_msg(func.__name__ + str(a))
        func(*a, **b)

    return do_it


registry = CommandRegistry()


def prepare(c):
    try:
        command_line = parse_command(c)
        matching_commands = registry.find(command_line.command)
        if len(matching_commands) == 0:
            raise NoMatchingCommand("Invalid command: " + command_line.command)
        if len(matching_commands) > 1:
            raise AmbiguousCommand("Ambiguous prefix. Possible commands: " + pretty_list(matching_commands),
                                   matching_commands)
        command = matching_commands[0]
        return Command(command, command_line.args)
    except InvalidCommandSyntax as e:
        raise e


def parse_command(c):
    s = tokenize_command(c)
    com = CommandLine(s)
    return com


def tokenize_command(c):
    s = c.strip().lower().split()
    return s


def execute(command, e, respond):
    log_msg([command, e.source])
    handler = registry.lookup(command)
    handler(command.args, e, respond)
