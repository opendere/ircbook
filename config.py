import pickle


class Configuration:
    def __init__(self, config_source):
        if isinstance(config_source, dict):
            self.con_dict = config_source
        else:
            with open(config_source, "rb") as cf:
                # File should contained a pickled dictionary with the relevant settings.
                # Connection info from conf.py file:
                con_dict = pickle.load(cf)
                self.channels = con_dict["channels"]
                self.owners = con_dict["owners"]
                self.active_channels = con_dict["active_channels"]
                self.con_dict = con_dict
                self.config_file = config_source

    def password(self):
        return self.con_dict["password"]

    def nick(self):
        return self.con_dict["nick"]

    def server(self):
        return self.con_dict["server"]

    def port(self):
        return self.con_dict["port"]

    def log_chan(self):
        return self.con_dict["logchan"]

    def get_channels(self):
        return self.con_dict["channels"]

    def add_channel(self, channel):
        self.con_dict["channels"].append(channel)

    def has_channel(self, channel):
        return channel in self.con_dict["channels"]

    def add_active_channel(self, channel):
        self.con_dict["active_channels"].append(channel)

    def remove_active_channel(self, channel):
        self.con_dict["active_channels"].remove(channel)

    def has_active_channel(self, channel):
        return channel in self.con_dict["active_channels"]

    def is_owner(self, user):
        return user in self.con_dict["owners"]

    def save(self):
        with open(self.config_file, "wb") as f:
            pickle.dump(self.con_dict, f)
