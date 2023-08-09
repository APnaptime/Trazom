import json
import asyncio
import subprocess
import os

import nextcord
import spotipy

from yt_dlp import YoutubeDL
from spotipy.oauth2 import SpotifyClientCredentials
from datetime import datetime
from requests import get

from trazom_utils import Track
from trazom_utils import QueryItem
from trazom_utils import PlayQueue
from trazom_utils import search

class Trazom():
    
    def __init__(self, interaction: nextcord.Interaction):

        # loading config
        try:
            config = json.load(open("myConfig.json"))
            cid = config["spotify_client_ID"]
            secret = config["spotify_app_secret"]
        except:
            print("Trazom: couldn't load config file!")
            return

        # spotify
        self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=secret))

        # queues for handleing inter-routine data
        self.player_queue = asyncio.Queue(maxsize = 2)  # downloaded tracks to be played by the player
        self.order_queue = asyncio.Queue(maxsize = 1)   # requests to download  processed query
        self.next_queue = asyncio.Queue(maxsize = 1)   # queue to handle listening for a song's end, num songs in = num songs to wait for
        self.query_queue = asyncio.Queue()

        self.track_queue = PlayQueue()                      # the player queue for processed tracks to be played, allows for custom sorting (vs default asyncio.Queue)
        self.vchannel = interaction.user.voice.channel      # channel to connect to, note this is not a connection yet
        self.tasks = None                                   # asyncio tasks trazom uses, to be canceled upon request or unload
        self.now_playing = None                               # the currently playing song
        
    

    # helper function: updates access time ex) https://techoverflow.net/2019/07/22/how-to-set-file-access-time-atime-in-python/
    # should always check to make sure file is in the pool first via song_in_pool
    def update_access_time(self, track: Track):
        now = datetime.now()
        print("now")
        fpath = os.path.abspath(track.play_file)
        print("path")
        stat = os.stat(fpath)
        print("stat")
        mtime = stat.st_mtime
        print("mtime")
        os.utime(fpath, times = (now.timestamp(), mtime))

    # coroutine for ordering the next song to play when the current one is finished playing
    async def next_track_handler(self):
        while True:
            #print("next handler initialized")

            #print("next handler start size: " + str(self.next_queue.qsize()))
            track = await self.next_queue.get()
            #print("next handler item got!")

            while True: # poll for the song end / skip
                await asyncio.sleep(1)
                if self.voice_client.is_playing():
                    continue # continue waiting
                else:
                    print("finished playing " + track.title)
                    self.now_playing = None
                    self.order_queue.put_nowait("item")
                    break

    # coroutine player that interfaces with the discord voice client
    async def player_handler(self):
        while True:
            track:Track = await self.player_queue.get()
            self.player_track = track.track_id

            if self.vchannel is None: # clear the queue
                self.order_queue.put_nowait("item")
                continue

            source = nextcord.FFmpegOpusAudio(track.play_file)

            # check if something is already playing
            if self.voice_client.is_playing():
                print("something already playing")
                self.voice_client.stop()

            self.now_playing = track

            self.voice_client.play(source)
            print("now playing " + track.title)
            await self.next_queue.put(track)
            

    async def query_handler(self):
        print("query_handler: started")
        while True:
            queryItem = await self.query_queue.get()
            print("query_handler: searching: " + queryItem.query)
            if "open.spotify.com" in queryItem.query:       # if its a spotify link
                try:
                    components = queryItem.query.split("/")         # manual spotify url processing
                    link_type = components[-2]                      # detect type from url
                    spotify_id = (components[-1].split("?"))[0]     # extract ID
                    tracks = []                                     # song names from the spotify link

                    if link_type == "playlist":
                        result = self.sp.playlist(spotify_id)
                        result_tracks = result['tracks']['items']   # search for the spotify ID
                        for item in result_tracks:
                            tracks.append(item['track']['name'] + " " + item['track']['artists'][0]['name'])    # for every song, youtube search: trackname + track artist

                    elif link_type == "track":                      # case single track
                        result = self.sp.track(spotify_id)
                        tracks.append(result['name'] + " " + result['artists'][0]['name'])  # youtube search: trackname + track artist

                    for track_query in tracks:
                        await asyncio.sleep(0)
                        songs = search(track_query)                 # perform the search on tracks[]
                        await asyncio.sleep(0)                      # search can be expensive so we pass off before and after
                        for song in songs:
                            self.track_queue.put(Track(song, queryItem.user, queryItem.id))
                        
                except:
                    print("ERROR: parsing spotify query: " + queryItem.query)
                    return
            
            else:                                                   # youtube search string / url
                songs = search(queryItem.query)
                for song in songs:
                    self.track_queue.put(Track(song, queryItem.user, queryItem.id))

    # coroutine that provides downloaded (and normalized) songs to the player via queue
    async def order_handler(self):
        print("Order handler started")
        # put in an order so we start playing immedietly
        self.order_queue.put_nowait("item")
        # loop for getting the order for the next song from the discord interface
        while True:
            order = await self.order_queue.get()  # wait on an order for the next song, like a notify mailbox
                                            # the contents of the order_queue are not relevent since
                                            # its only being used as a messaging system between coroutines
            print("new order found!")

            # free the baton for discord interface to respond
            await asyncio.sleep(0.5)

            # now a song is requested, get the next track to be played
            track = await self.track_queue.get()

            print("trazom - order handler: fetching track")
            fname = await track.fetch_track(5)
            print(fname)

            if fname is None:
                print("trazom - order handler: fetch was none")
                continue

            print("DL complete, sending to player")
            await self.player_queue.put(track)


    async def start_tasks(self):
        # connect to the voice channel
        self.voice_client = await self.vchannel.connect()
        print("trazom connected to voice")

        # tasks for trazom
        self.tasks = [
            asyncio.create_task(self.next_track_handler()),
            asyncio.create_task(self.player_handler()),
            asyncio.create_task(self.order_handler()),
            asyncio.create_task(self.query_handler())
        ]

        # wait for them to cancel
        for task in self.tasks:
            try:
                await task
            except asyncio.CancelledError as e:
                print(task.get_name() + " cancelled!")

        # all tasks cancelled
        print("trazom tasks collected!")
        await self.voice_client.disconnect()


    # non async wrapper function for starting the music bot
    def start(self):
        # call the async functions required to start the bot
        self.task = asyncio.create_task(self.start_tasks())

    ## methods that discord commands call to interface with trazom
    
    # adds a song request (yt url, spotify url, string search) to be played
    async def play(self, interaction: nextcord.Interaction, query: str):
        queryItem = QueryItem(query, interaction)
        print("putting " + query + " into query_queue")
        self.query_queue.put_nowait(queryItem)


    # gets the list representation of the current play queue
    def get_queue(self):
        return self.track_queue.get_embed(self.now_playing)
        
    
    # orders a new song to be played or current one to stop if there is no songs left
    def skip(self):
        self.voice_client.stop()


    # removes the track at a given index from the play queue
    def remove_track(self, interaction: nextcord.Interaction, track_index: int):
        pass
        
    # stops the bot
    def stop(self):
        print("trazom: stop called")
        if self.tasks is None:
            return
        for task in self.tasks:
            print("trazom: cancel " + str(task.cancel()))
        
