import asyncio
from asyncio import Queue
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json
from asyncio import Queue
from pytube import YouTube
from pytube import Search
import subprocess
import os
from TrazomDiscordInterface import QueryItem
from requests import get
from yt_dlp import YoutubeDL

class Track:
    def __init__(self, track, user: str, user_id: int):
        self.filename = track["id"]
        self.filepath = None
        self.title = track["title"]
        self.URL = track["url"]
        self.requester = user
        self.user_id = user_id
        self.duration = None
        self.yt = None
        self.streams = None

class main:
    def __init__(self, cid, secret, query_queue : Queue, player_queue : Queue, order_queue: Queue):
        self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=cid, client_secret=secret))

        # external Queues
        self.query_queue = query_queue
        self.player_queue = player_queue
        self.order_queue = order_queue

        # internal tracks
        self.played_list = []
        self.queue_list = []

    # get a string query and convert it to a track data structure for easy handling / display
    async def query_parser(self):

        def query_cb(d):
            if d["status"] == "finished":
                print("Download complete")

        
        def search(queryItem: QueryItem):
            print("searching ...")
            if queryItem.layer == 0:
                #, 
                YDL_OPTIONS = {'extract_flat' : True, 'format': 'bestaudio'}
            else:
                YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist':'True'}
            with YoutubeDL(YDL_OPTIONS) as ydl:
                try:
                    print("try")
                    get(queryItem.query) 
                except:
                    print("except")
                    video = ydl.extract_info(f"ytsearch1:{queryItem.query}", download=False)['entries'][0]
                else:
                    print("else")
                    video = ydl.extract_info(queryItem.query, download=False)

            return video

        while True:
            # get a query from the discord interface (str), this is a blocking call to wait for a request
            queryItem:QueryItem = await self.query_queue.get()


            # handoff to let the discord bot send it's response
            await asyncio.sleep(0.01)

            # check the string for indicators of special handling
            # - spotify (track, playlist)
            # - youtube (track, playlist)
            # else youtube search the string query

            # spotify link
            if "open.spotify.com" in queryItem.query:

                # get the ID and type from the URL
                try:
                    components = queryItem.query.split("/")
                    link_type = components[-2]
                    spotify_id = (components[-1].split("?"))[0]
                except:
                    print("ERROR: parsing spotify query: " + queryItem.query)
                    continue
            
            else:
                print("string query processing")
                song = search(queryItem)
                ##print(song["title"])
                print(song.keys())
                track = Track(song, queryItem.user, queryItem.id)
                print(track.title)
                self.queue_list.append(track)

    # request a song to be downloaded 
    async def download_track(self, track: Track, notify: Queue):
        print("in download func: ")

        # callback for when a download is completed
        def dl_callback(d):
            if d["status"] == "finished":
                print("Download complete!!!")
                input_file = d['filename']
                output_name = track.filename
                subprocess.run(["ffmpeg-normalize", input_file, "-o", output_name + ".webm", "-c:a", "libopus", "-t", "-14", "--keep-lra-above-loudness-range-target", "-f"])
                print("conversion done!")
                notify.put_nowait(track)

        urls = [track.URL]

        ydl_opts = {
            'format': 'm4a/bestaudio/best'
            # ℹ️ See help(yt_dlp.postprocessor) for a list of available Postprocessors and their arguments
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.add_progress_hook(dl_callback)
            error_code = ydl.download(urls)
        

    async def order_handler(self):
        print("Order handler started")

        # loop for getting the order for the next song from the discord interface
        while True:
            order = await self.order_queue.get()  # wait on an order for the next song, like a notify mailbox
                                            # the contents of the order_queue are not relevent since
                                            # its only being used as a messaging system between coroutines

            # free the baton for discord interface to respond
            await asyncio.sleep(0.01)

            # now a song is requested, download the next track
            print("new order found!")
            if len(self.queue_list) > 0:    # make sure there is a song to play
                print("starting order processing")
                # queue to get notified through for waiting for download completion
                notify_queue = Queue()
                track = self.queue_list.pop(0)
                print("calling DL")
                await self.download_track(track, notify_queue)   # request the download
                await notify_queue.get()
            else:
                print("order requested but list empty?")



    async def start(self):
        query_parse_task = asyncio.create_task(self.query_parser())
        order_handler_task = asyncio.create_task(self.order_handler())
        await query_parse_task
        await order_handler_task





                