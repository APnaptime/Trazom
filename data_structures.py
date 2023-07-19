import discord

class Track:
    def __init__(self, track, user: str, user_id: int):
        self.filename = track["id"]
        self.inputfile = None
        self.filepath = None
        self.dl_requested = False
        self.title = track["title"]
        self.URL = track["url"]
        self.requester = user
        self.user_id = user_id
        self.duration = None
        self.yt = None
        self.streams = None

# object to hold query requests and associated requester
class QueryItem:
    def __init__(self, query: str, context: discord.Interaction):
        self.query = query
        self.user = context.user.display_name
        self.id = context.user.id
        self.layer = 0