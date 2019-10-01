from json import load, dump

from twython import Twython

# Read Twitter secrets.
with open("twitter-secrets.json", "r") as f:
    secrets = load(f)

twitter = Twython(secrets["key"], secrets["key_secret"])
auth = twitter.get_authentication_tokens()
oauth_token = auth["oauth_token"]
oauth_secret = auth["oauth_token_secret"]
print(auth["auth_url"])
auth_verifier = input("Enter PIN: ")
twitter = Twython(secrets["key"], secrets["key_secret"],
                  oauth_token, oauth_secret)
tokens = twitter.get_authorized_tokens(auth_verifier)
secrets["token"] = tokens["oauth_token"]
secrets["token_secret"] = tokens["oauth_token_secret"]
with open("twitter-secrets.json", "w") as f:
    dump(secrets, f, indent=1)
