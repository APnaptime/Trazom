import asyncio
import subprocess
import nextcord
import os
import datetime
import trazom_config

from yt_dlp import YoutubeDL
from requests import get



class Track:

    def __init__(self, track, user, user_id: int):

        # file management fields
        self.filename = track["id"]                             # we choose the name to be the id (Xyz4e... etc.)
        self.download_file = None                               # written to when the track is downloaded but not normalized
        self.normalized_file = None                             # the file to write the normalized track to
        self.play_file = None

        self.title = track["title"]             # user facing title of track
        self.URL:str = track["url"]             # URL to download from with yt-dlp
        self.requester = user                   # user who requested
        self.user_id = user_id                  # unique ID for requester
        self.duration = int(track["duration"])  # length of track in seconds

        self.disp_duration = str(self.duration // 60) + ":" + "{secs:0>2}".format(secs=str(self.duration % 60))
        self.dl_proc = None
        self.norm_listener = None
        self.norm_proc = None
        self.fetch_requested = False

        self.track_id = 0 # a unique identifier for a single track instance

    def req_dl(self):
        # print("req_dl: started!")
        # do we already have a downloaded file
        fname = find_file(os.path.join('.',trazom_config.dl_folder), self.filename)
        #print("req_dl: - " + str(self.title) +  " : " + str(fname))
        if fname is not None: # we found a good file, set the name just in case we haven't already
            self.download_file =  os.path.join(trazom_config.dl_folder, fname) # trazom_config.dl_folder + "/" + fname
            return

        else:
            # we didn't find the file, are we already downloading something?

            # if we haven't started download (or download is finished but we didn't find the file), start the download in a subprocess
            if self.dl_proc is None or self.dl_proc.poll() is not None: 
                # empty some space!
                clear_space(trazom_config.dl_clear, trazom_config.dl_allocated, os.path.join('.',trazom_config.dl_folder))
                print("Started Downloading " + self.title)
                self.dl_proc = subprocess.Popen(['yt-dlp', '--quiet', '-f', 'ba', self.URL, '-o', trazom_config.dl_folder + '/%(id)s.%(ext)s'], shell = False)
                
                return
            
            # otherwise, we are currently downloading since poll didn't return none so we can just wait / do nothing and return            

    async def schedule_norm(self):
        # sanity check that we don't already have a normalized file
        if find_file(os.path.join('.',trazom_config.norm_folder), self.filename) is not None:
            # print("scheduling norm, already normalized file")
            self.norm_listener = None
            return

        self.req_dl() # request that we start the download if it hasn't already finished 

        while self.dl_proc is not None and self.dl_proc.poll() is None:
            
            if self.fetch_requested:
                await asyncio.sleep(trazom_config.download_wait_after_fetch)
                break

            await asyncio.sleep(trazom_config.sleep_frequency)

        # now proc should be concluded
        fname = find_file(os.path.join('.',trazom_config.dl_folder), self.filename)

        # double check it does exist
        if fname is None:
            #print("norm schedule: dl finished but no file found?")
            self.norm_listener = None
            return
        else: # otherwise, schedule the norm
            # print("norm: dl finished, starting norm")
            self.download_file = os.path.join(trazom_config.dl_folder, fname) # trazom_config.dl_folder + "/" + fname
            if self.norm_proc is None or self.norm_proc.poll() is not None:
                clear_space(trazom_config.norm_clear, trazom_config.norm_allocated, os.path.join('.',trazom_config.norm_folder))
                print("Started Normalizing " + self.title)

                # trazom_config.norm_folder + "/" + self.filename + ".wav" "-b:a", "64k", 
                self.norm_proc = subprocess.Popen(["ffmpeg-normalize", self.download_file, "-t", "-30", "-lrt", "7", "--keep-lra-above-loudness-range-target", "-f",  "-c:a", "libopus", "-b:a", "64k", "-o", os.path.join(trazom_config.norm_folder, self.filename) + ".opus"], shell = False) # "-c:a", "pcm_s16le", 
                self.norm_listener = None
                return


    # wrapper function for requesting a normalize operation to be performed. Unlike req_dl, this requires waiting for a download
    # to have been performed so we have to make a new asyncio task to poll / detect the download finish
    def req_norm(self):
        # do we already have a normalized file?
        fname = find_file(os.path.join('.',trazom_config.norm_folder), self.filename)

        if fname is not None: # we found a good file, set the name just in case we haven't already
            # print("req norm: file already found")
            self.normalized_file = os.path.join(trazom_config.norm_folder, fname) # trazom_config.norm_folder + "/" + fname
            return

        elif self.norm_listener is not None: # if we've already started the task
            # print("red norm: listener already started")
            return
        
        else: # otherwise we are clear to wait
            self.norm_listener = asyncio.create_task(self.schedule_norm())
        
    async def fetch_track(self, deadline):
        self.fetch_requested = True

        fname = find_file(os.path.join('.',trazom_config.norm_folder), self.filename) 
        if fname is not None:
            # print("fetch: norm found")
            self.normalized_file = os.path.join(trazom_config.norm_folder, fname) # trazom_config.norm_folder + "/" + fname
            self.play_file = self.normalized_file
            return self.play_file
        
        # otherwise, start the countdown on us needing the track

        self.req_norm() # request that the track be normalized

        # detect where we are in the waiting phase, are we downloading? (listener will be a task)
        if self.norm_listener is not None:
            # print("fetch: listener not none")
            await self.norm_listener

        # wait a short time for norm to finish!
        elapsed = 0
        while elapsed < deadline:

            fname = find_file(os.path.join('.',trazom_config.norm_folder), self.filename)
            if fname is not None:
                self.normalized_file = os.path.join(trazom_config.norm_folder, fname) # trazom_config.norm_folder + "/" + fname
                self.play_file = self.normalized_file
                return self.normalized_file

            await asyncio.sleep(trazom_config.sleep_frequency)
            elapsed = elapsed + trazom_config.sleep_frequency

        # if we've reached here, that means we're past our deadline, so start looking for alternatives!
        fname = find_file(os.path.join('.',trazom_config.dl_folder), self.filename)
        if fname is not None:
            # print("fetch: returning dl ver")
            self.download_file = os.path.join(trazom_config.dl_folder, fname) # trazom_config.dl_folder + "/" + fname
            self.play_file = self.download_file
            return self.play_file
        
        # otherwise we don't have a file to return
        return None
    
    def get_status(self):

        if find_file(os.path.join('.',trazom_config.norm_folder), self.filename) is not None:
            return "On Deck            "
        
        if self.norm_proc is not None and self.norm_proc.poll() is None:
            return "Climbing the stairs"

        if find_file(os.path.join('.',trazom_config.dl_folder), self.filename) is not None:
            return "In the hold        "
        
        if self.dl_proc is not None and self.dl_proc.poll() is None:
            return "Exiting cabin      "
        
        return     "Sleeping           "
    
    async def cleanup(self):
        if self.norm_listener is not None:
            self.norm_listener.cancel()
            try:
                await self.norm_listener
            except asyncio.CancelledError as e:
                pass

# object to hold query requests and associated requester
class QueryItem:
    def __init__(self, query: str, interaction: nextcord.Interaction):
        self.query = query
        self.user = interaction.user
        self.id = interaction.user.id
        self.layer = 0

class PlayQueue:
    def __init__(self):
        self.track_queue = asyncio.Queue()
        self.played = []
        self.time_skipped = {}
        self.time_played : dict[int, int] = {}
        self.player_songs : dict[int, asyncio.Queue] = {} 
        self.track_id = 0 # for assigning unique IDs to added tracks
        self.q_size = 0 # internal tracker for how many tracks are to be played

    # updates the list by overrideing with the queue contents
    # at the end, the list is overwritten and the queue is unchanged
    def reconcile(self):
        track_list = []
        #print("reconciling q of size: " + str(self.track_queue.qsize()))
        for i in range(0, self.track_queue.qsize()):
            item = self.track_queue.get_nowait()
            track_list.append(item)
            self.track_queue.put_nowait(item)
        return track_list

    def get_embed(self, now_playing: Track, footer = None):
        track_list = self.reconcile()
        title = "Trazom Music Bot :notes:"

        if now_playing is not None:
            title = ":notes: Now Playing : " + now_playing.title + " `" + now_playing.disp_duration + "`"

        tracks = ""
        index = 1
        num_tracks = self.tracks_remaining() 
        track_num_display = "Displayed tracks: " + str(trazom_config.q_disp_max_tracks) + "/" + str(num_tracks) if num_tracks > trazom_config.q_disp_max_tracks else "Displayed tracks: " + str(num_tracks)
        if footer is None:
            footer = track_num_display

        for track in track_list:
            fixed_title = str(track.title).ljust(trazom_config.q_disp_title_max_char) if len(track.title) < trazom_config.q_disp_title_max_char else track.title[0:trazom_config.q_disp_title_max_char - 3] + "..."
            tracks = tracks + str(index) + " - " + "[" + track.disp_duration + "]\t`" + fixed_title + "` " + track.requester.mention + "\n"
            index = index + 1
            if index > trazom_config.q_disp_max_tracks:
                break

        embed = nextcord.Embed(title = title, description = tracks)
        embed.set_footer(text = footer)

        return embed

    def get_session_summary(self):
        if len(self.played) == 0:
            return nextcord.Embed(title = ":notes: Trazom complete!", description = "~Tune in next time~")

        tracks = ""
        index = 1
        for track in self.played:
            fixed_title = str(track.title).ljust(trazom_config.q_disp_title_max_char) if len(track.title) < trazom_config.q_disp_title_max_char else track.title[0:trazom_config.q_disp_title_max_char - 3] + "..."
            tracks = tracks + str(index) + " - " + "[" + track.disp_duration + "]\t`" + fixed_title + "` " + track.requester.mention + "\n"
            index = index + 1
        embed = nextcord.Embed(title = ":notes: Trazom complete!", description = tracks)
        return embed

    # reorders the playqueue to be based on time
    def time_priority(self):
        
        if self.track_queue.qsize() >= trazom_config.q_disp_max_tracks:   # do we need to add something to the front section of the queue?
            return                                                      # if not, we can just keep the back as a dict

        # now we need to update the queue
        # first, get the queue as a list and empty the queue
        displayed_tracks = []
        for i in range(0, self.track_queue.qsize()):
            item = self.track_queue.get_nowait()
            displayed_tracks.append(item)

        time_tally = dict(self.time_played)

        # create a list of songs to be sorted, order by first requested for ease of algorithm later
        to_sort = sorted(displayed_tracks, key=lambda x: x.track_id)


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
        #print("time prio: algorithm")

        while len(time_sorted) < trazom_config.q_disp_max_tracks:

            # find users to check
            users = set()
            for track in to_sort:
                users.add(track.user_id)
            
            for user, queue in self.player_songs.items():
                if queue.qsize() > 0:
                    users.add(user)

            if len(users) < 1:
                break # no more songs to sort so exit

            # now we have a list of valid users to check
            # initial values for finding min T
            lowest_u = list(users)[0]
            lowest_t = time_tally[lowest_u]
            #print("lowest u: " + str(to_sort[0].requester))
            #print("lowest t: " + str(lowest_t))

            # figure out who should go next
            for user in users:
                if time_tally[user] < lowest_t:
                    lowest_t = time_tally[user]
                    lowest_u = user
            
            # lowest found, add it to the list
            list_found = False
            for track in to_sort:
                if track.user_id == lowest_u:
                    #print("lowest user track found")
                    list_found = True
                    to_sort.remove(track)
                    time_sorted.append(track)
                    time_tally[lowest_u] = time_tally[lowest_u] + track.duration
                    break

            # if we've successfuly found the track in the display list
            if list_found:
                continue

            # otherwise we have to get the track from the player_songs
            track = self.player_songs[lowest_u].get_nowait()
            time_sorted.append(track)
            time_tally[lowest_u] = time_tally[lowest_u] + track.duration

        # everything is now sorted

        # put the sorted list into the old empty queue
        for track in time_sorted:
            self.track_queue.put_nowait(track)


    def tracks_remaining(self):
        return self.q_size
    
    def on_deck(self):
        track_list = self.reconcile() # get the list representation
        if len(track_list) >= 1:
            return track_list[0]
        else:
            return None

    def in_the_hold(self):
        track_list = self.reconcile()
        if len(track_list) >= 2:
            return track_list[1]
        else:
            return None


    def notify_skipped(self, track, duration):
        if track.user_id in self.time_skipped.keys():
            self.time_skipped[track.user_id] = self.time_skipped[track.user_id] + duration
        else:
            self.time_skipped[track.user_id] = duration

    async def get(self):
        # maintain the sorted order for the displayed songs
        self.time_priority()
        
        track = await self.track_queue.get()
        self.q_size = self.q_size - 1
        self.played.append(track)
        if self.on_deck() is not None:
            self.on_deck().req_norm()
        if self.in_the_hold() is not None:
            self.in_the_hold().req_dl()
        if track.user_id not in self.time_played.keys():  # initialize the time tracker if not already

            self.time_played[track.user_id] = track.duration
        else:
            self.time_played[track.user_id] = self.time_played[track.user_id] + track.duration

        return track

    def put(self, track : Track):
        # increment the unique ID for the track
        track.track_id = self.track_id
        self.track_id = self.track_id + 1

        self.q_size = self.q_size + 1

        # rare case, if we need to start processing immediately 
        if self.track_queue.qsize() < 2:
            #print("put requesting DL")
            track.req_dl()
        if self.track_queue.qsize() < 1:
            #print("put requesting Norm")
            track.req_norm()

        if track.user_id not in self.time_played.keys():  # initialize the time tracker if not already
            self.time_played[track.user_id] = 0

        if track.user_id not in self.player_songs.keys(): # initialize the songqueue for this user if not already
            self.player_songs[track.user_id] = asyncio.Queue()
        
        # and now we put the song in the queue for the user
        self.player_songs[track.user_id].put_nowait(track)

        # maintain the sorted order for the displayed songs
        self.time_priority()
        
    async def remove(self, index: int):

        track_list = self.reconcile()

        if index not in range(0,len(track_list)):
            return None
        
        else:
            # remove the item:
            removed = track_list.pop(index)
            
            await removed.cleanup()

            for i in range(0, self.track_queue.qsize()): # empty the queue
                item = self.track_queue.get_nowait()

            for track in track_list:   # populate the queue again
                self.track_queue.put_nowait(track)

            self.q_size = self.q_size - 1

            self.time_priority()

            return removed

    
# looks for and returns the complete file name of the first instance of a match given a directory and a part of a file name 
def find_file(loc, search):
    fnames = [f for f in os.listdir(loc)]
    for name in fnames:
        if search in name:
            return name
    return None

# sends a reply to a defered command response that will delete itself after a set time
async def short_response(interaction: nextcord.Interaction, response, delay = trazom_config.reply_default_lifespan):
    msg = await interaction.followup.send(content = response, suppress_embeds = True)
    if delay < 0: # if its negative, then don't delete
        return
    await asyncio.sleep(delay)
    await msg.delete()

def search(query):
    YDL_OPTIONS = {'extract_flat' : True, 'format': 'bestaudio', 'noplaylist': False, 'quiet': True}
    with YoutubeDL(YDL_OPTIONS) as ydl:
        try: # test the link
            get(query)
        except: # not a yt link, traat as string search
            video = ydl.extract_info(f"ytsearch1:{query}", download=False)['entries'][0]
            return [video]
        else: # yt link, can be playlist OR single track
            videos = ydl.extract_info(query, download=False)

            if 'entries' in videos:
                return videos['entries']
            else:
                return [videos]

# helper function: updates access time ex) https://techoverflow.net/2019/07/22/how-to-set-file-access-time-atime-in-python/
# should always check to make sure file is in the pool first via song_in_pool
def update_access_time(track: Track):
    try:
        now = datetime.datetime.now()
        # print("now")
        fpath = os.path.abspath(track.play_file)
        # print("path")
        stat = os.stat(fpath)
        # print("stat")
        mtime = stat.st_mtime
        # print("mtime")
        os.utime(fpath, times = (now.timestamp(), mtime))
        return True
    except:
        return False
    
def clear_space(needed: int, allocated: int, location):

    if needed < 0:
        print("clear_space: needed is negative")
        return False

    if allocated < 0:
        print("clear_space: allocated is negative")
        return False
    
    if needed > allocated:
        print("clear_space: total size greater than allocated!")
        return False

    fnames = [f for f in os.listdir(location)]
    files = []
    total_size = 0
    for name in fnames:
        path = os.path.abspath(os.path.join(location, name))
        stats = os.stat(path)
        size = stats.st_size
        last_touched = stats.st_mtime
        files.append((last_touched, path, size)) # add a tuple to the list
        total_size = total_size + size

    #print("clear_space: current:" + str(total_size) + " out of " + str(allocated) + " allocated")

    if total_size + needed < allocated: # then we have enough space
        #print("clear_space: enough already")
        return True
    
    # otherwise start reducing

    sorted_files = sorted(files) # will sort by first element of tuple by default from newest to oldest
    
    while total_size + needed > allocated:
        item = sorted_files.pop(0) # get oldest item
        total_size = total_size - item[2]
        try:
            os.remove(item[1])
        except PermissionError:
            print("clear_space: deleting cancelled " + str(item[1]))
            return False

    #print("clear_space: finished, current " + str(total_size) + " out of " + str(allocated) + " allocated")
    return True
    
    
