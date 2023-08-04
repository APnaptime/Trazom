import discord
import asyncio

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

class PlayQueue:
    def __init__(self):
        self.track_queue = asyncio.Queue()
        self.track_list = []
        self.played = []
        self.time_skipped = {}

    def debug_dump(self):
        self.reconcile()
        print(" == tracks == ")
        for track in self.track_list:
            print(str(track.title) + " submitted by: " + str(track.requester) + " Index: " + str(track.track_id))


    # updates the list by overrideing with the queue contents
    # at the end, the list is overwritten and the queue is unchanged
    def reconcile(self):
        self.track_list = []
        print("reconciling q of size: " + str(self.track_queue.qsize()))
        for i in range(0, self.track_queue.qsize()):
            item = self.track_queue.get_nowait()
            self.track_list.append(item)
            self.track_queue.put_nowait(item)

    # reorders the playqueue to be based on time
    def time_priority(self):
        self.reconcile()

        if len(self.track_list) == 0:
            print("time sort: empty list")
            return

        time_tally = {} # people : player time used
        people = []

        # get all tracks and their authors
        for track in self.played:
            if not track.user_id in time_tally.keys():
                time_tally[track.user_id] = 0

        for track in self.track_list:
            if not track.user_id in time_tally.keys():
                time_tally[track.user_id] = 0
        
        # now count the prior time played
        for track in self.played:
            time_tally[track.user_id] = time_tally[track.user_id] + track.duration

        # and subtract any skipped duration
        for uid in self.time_skipped.keys():
            time_tally[uid] = time_tally[uid] - self.time_skipped[uid]

        # create a list of songs to be sorted, order by first requested for ease of algorithm later
        to_sort = sorted(self.track_list, key=lambda x: x.track_id)
        time_sorted = []

        # now we have a time talley, we can order the songs via the following algorithm:
        #
        #          u = user_id
        #       T[u] = total time of songs so far in the list for a user u
        #       
        #       1) find the u with lowest T[u]
        #       2) iterate through unsorted songs via song_id (in order of requested / timestamp)
        #          select the first song where T[song u] is minimized among [t[u]] of unsorted songs
        #       3) append the selected song to the sorted list and add the song duration to T[u]
        #       4) repeat until no songs remain unsorted

        while len(to_sort) > 0:
            # finding the lowest T[u]
            
            # initial values for finding min T
            lowest_u = to_sort[0].user_id
            lowest_t = time_tally[lowest_u]

            # get the user_ids to be sorted
            users = set()
            for track in to_sort:
                users.add(track.user_id)

            # find the lowest T[u]
            for user in users:
                if time_tally[user] > lowest_t:
                    lowest_t = time_tally[user]
                    lowest_u = user
            
            # lowest found, add it to the list
            for track in to_sort:
                if track.user_id == lowest_u:
                    to_sort.remove(track)
                    time_sorted.append(track)
                    time_tally[track.user_id] = time_tally[track.user_id] + track.duration
                    break

        # everything is now sorted

        # empty the old queue
        for i in range(0, self.track_queue.qsize()):
            self.track_queue.get_nowait()

        # put the sorted list into the now empty queue
        for track in time_sorted:
            self.track_queue.put_nowait(track)

        # update the list as well
        self.track_list = time_sorted
        
    def notify_skipped(self, track, duration):
        if track.user_id in self.time_skipped.keys:
            self.time_skipped[track.user_id] = self.time_skipped[track.user_id] + duration
        else:
            self.time_skipped[track.user_id] = duration

    async def get(self):
        track = await self.track_queue.get()
        self.played.append(track)
        return track

    def put(self, track):
        print("putting in")
        self.track_queue.put_nowait(track)
        self.reconcile()
        self.time_priority()
        

    