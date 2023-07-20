import discord

class Track:
    id = 0
    def __init__(self, track, user: str, user_id: int):
        self.filename = track["id"]
        self.inputfile = None
        self.filepath = "songPool/" + self.filename + ".webm"
        self.dl_requested = False
        self.title = track["title"]
        self.URL = track["url"]
        self.requester = user
        self.user_id = user_id
        self.duration = int(track["duration"])
        self.yt = None
        self.streams = None
        self.track_id = Track.id # a unique identifier for a single track instance
        Track.id = Track.id + 1  


# object to hold query requests and associated requester
class QueryItem:
    def __init__(self, query: str, context: discord.Interaction):
        self.query = query
        self.user = context.user.display_name
        self.id = context.user.id
        self.layer = 0