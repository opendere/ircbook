# Copyright (c) 2016 the IrcBook team
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

import random


class Instruments:
    def __init__(self):
        self.id_instrument_map = {}

    def add_instrument(self, instrument):
        if instrument.instrument_id is None:
            instrument.set_instrument_id(self._new_unique_id())
        inst_id = instrument.instrument_id

        if inst_id in self.id_instrument_map:
            raise ValueError("Already used instrument_id " + str(inst_id))

        elif not isinstance(inst_id, str):
            raise TypeError("instrument_id must be a str")

        self.id_instrument_map[inst_id] = instrument

        return instrument.instrument_id

    def get_instrument(self, instrument_id):
        return self.id_instrument_map[instrument_id]

    def _new_unique_id(self):
        """
        Generates a new unique ID in the form of a hex code represented
        as a string. Generates a random number between 1 and 100 times
        the number of keys, so it is guaranteed to succeed on the first
        try 99% of the time.
        """
        num_keys = len(self.id_instrument_map)
        while True:
            num = random.randint(0, (num_keys + 1) * 100)
            inst_id = "%0.2X" % num
            if inst_id not in self.id_instrument_map:
                return inst_id


class Instrument:
    def __init__(self, text, oracle_count_threshold, oracles, instrument_id=None):
        self.text = text
        self.oracle_count_threshold = oracle_count_threshold
        self.oracles = oracles
        self.instrument_id = instrument_id
        self.votes = {True: set(), False: set()}

    def set_instrument_id(self, instrument_id):
        """
        set a new unique ID for instrument
        """
        self.instrument_id = instrument_id

    def add_true_vote(self, name):
        self.votes[True].add(name)

    def add_false_vote(self, name):
        self.votes[False].add(name)

    def get_votes(self):
        return self.votes
