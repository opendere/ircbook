from json import load

from twython import Twython, TwythonStreamer

# Get tokens.
with open("twitter-secrets.json", "r") as f:
    secrets = load(f)


class MyStreamer(TwythonStreamer):
    def __init__(self, *args, **kwargs):
        self.t_object = Twython(secrets["key"], secrets["key_secret"],
                                secrets["token"], secrets["token_secret"])
        self.info = self.t_object.verify_credentials()
        self.uid = self.info["id"]
        super(MyStreamer, self).__init__(*args, **kwargs)

    def on_success(self, data):
        if "event" in data:
            print("Event!")
            if data["event"] == "follow":
                print("Following related!")
                uid = data["source"]["id"]
                if uid != self.uid:
                    print("Following " + data["source"]["screen_name"])
                    self.t_object.create_friendship(id=uid)
        print("Tick!")

    def on_error(self, status_code, data):
        print(status_code)


twitter = MyStreamer(secrets["key"], secrets["key_secret"],
                     secrets["token"], secrets["token_secret"])
twitter.user()
