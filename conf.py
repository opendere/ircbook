import pickle

x = {
    'server': 'irc.freenode.org',
    'nick': 'xenobook',
    'password': 'foo.py',
    'port': 6667,
    'logchan': '##xenolog',
    'channels': ['##xenobook'],
    'owners': ['xeno!~xeno@unaffiliated/xeno'],
    'active_channels': ['##xenobook']
}

with open("conf", "wb") as cf:
    pickle.dump(x, cf, pickle.HIGHEST_PROTOCOL)
