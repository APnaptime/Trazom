import asyncio
from asyncio import Queue
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json
from asyncio import Queue
import subprocess
import os
from shlex import quote
from requests import get
from yt_dlp import YoutubeDL
from data_structures import Track
from data_structures import QueryItem
from datetime import datetime

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
        

    def to_list(queue: Queue):
        ret_list = []
        for index in range(queue.qsize()):
            item = queue.get_nowait()
            ret_list.append(item)
            queue.put_nowait(item)
        return ret_list

    # get a string query and convert it to a track data structure for easy handling / display
    async def query_parser(self):

        def query_cb(d):
            if d["status"] == "finished":
                print("Download complete")

        
        async def search(query):
            await asyncio.sleep(0.5)
            print("searching ...")
            YDL_OPTIONS = {'extract_flat' : 'in_playlist', 'format': 'bestaudio', 'noplaylist': False}

            with YoutubeDL(YDL_OPTIONS) as ydl:
                try: # test the link
                    print("try")
                    get(query)
                except: # not a yt link, traat as string search
                    print("except")
                    video = YoutubeDL({'extract_flat' : True, 'format': 'bestaudio', 'noplaylist': True}).extract_info(f"ytsearch1:{query}", download=False)['entries'][0]
                    return [video]
                else: # yt link, can be playlist OR single track
                    print("else")
                    videos = ydl.extract_info(query, download=False)
                    print("done")

                    if 'entries' in videos:
                        return videos['entries']
                    else:
                        print(videos['title'])
                        print(videos.keys())
                        print(videos['format'])
                        print(videos['audio_ext'])
                        return [videos]
                    


        while True:
            # get a query from the discord interface (str), this is a blocking call to wait for a request
            queryItem:QueryItem = await self.query_queue.get()

            # handoff to let the discord bot send it's response
            await asyncio.sleep(0.5)

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
                    print("type: " + link_type + " id: " + spotify_id)
                    tracks = []
                    if link_type == "playlist":
                        result = self.sp.playlist(spotify_id)
                        result_tracks = result['tracks']['items']
                        for item in result_tracks:
                            tracks.append(item['track']['name'] + " " + item['track']['artists'][0]['name'])
                    elif link_type == "track":
                        result = self.sp.track(spotify_id)
                        tracks.append(result['name'] + " " + result['artists'][0]['name'])

                    print(tracks)

                    for track_query in tracks:
                        songs = await search(track_query)
                        for song in songs:
                            self.queue_list.append(Track(song, queryItem.user, queryItem.id))
                        
                except:
                    print("ERROR: parsing spotify query: " + queryItem.query)
                    continue
            
            else: # youtube search string / url
                print("string query processing")
                songs = await search(queryItem.query)
                print("returned sq")
                for song in songs:
                    self.queue_list.append(Track(song, queryItem.user, queryItem.id))

    # calls a command with popen and polls on an interval to check completion
    async def wait_cmd(self, cmd):
        print("cmd called")
        passed = 0
        proc = subprocess.Popen(cmd, shell = True)
        while True:
            if proc.poll() is None:
                print("cmd poll waiting " + str(passed))
                passed = passed + 1
                await asyncio.sleep(1)
            else:
                print("cmd poll done")
                return

    # updates access time ex) https://techoverflow.net/2019/07/22/how-to-set-file-access-time-atime-in-python/
    # should always check to make sure file is in the pool first
    def update_access_time(self, track: Track):
        now = datetime.now()
        print("now")
        fpath = os.path.abspath(track.filepath)
        print("path")
        stat = os.stat(fpath)
        print("stat")
        mtime = stat.st_mtime
        print("mtime")
        os.utime(fpath, times = (now.timestamp(), mtime))

    def song_in_pool(self, track: Track):
        print("starting pool search")
        fnames = [f for f in os.listdir(os.path.join('.','songPool'))]
        print(fnames)
        print("looking for: " + track.filename + ".webm" + " in list:")
        res = track.filename + ".webm" in fnames
        if res is True:
            print("found, updating")
            self.update_access_time(track)
        return res

    def clear_space_for(self, track: Track):
        capacity = 500 * 1000000

    async def normalize_track(self, track):
            # old version, blocking call
        

        print("norm started!")

        #subprocess.run(["ffmpeg-normalize", track.inputfile, "-o", track.filepath, "-c:a", "libopus", "-t", "-14", "--keep-lra-above-loudness-range-target", "-f"])
        await self.wait_cmd(["ffmpeg-normalize", track.inputfile, "-o", track.filepath, "-c:a", "libopus", "-t", "-14", "--keep-lra-above-loudness-range-target", "-f"])

            # new await integration for shell commands from https://docs.python.org/3/library/asyncio-subprocess.html
            # ["ffmpeg-normalize", track.inputfile, "-o", track.filepath, "-c:a", "libopus", "-t", "-14", "--keep-lra-above-loudness-range-target", "-f"]
            # cmd = "ffmpeg-normalize " + quote(track.inputfile) + " -o " + quote(track.filepath) + " -c:a libopus -t -14 --keep-lra-above-loudness-range-target -f"
            # proc = await asyncio.create_subprocess_shell(
            # cmd,
            # stdout = asyncio.subprocess.PIPE,
            # stderr = asyncio.subprocess.PIPE)

        print("norm finished!")

        os.remove(track.inputfile)

    # request a song to be downloaded 
    async def download_track(self, track: Track):
        print("download started!")
        #   queue for download completion signaling
        notify = Queue()

            # callback for when a download is completed
        def dl_callback(d):
            min_wait = 5 # after 5 seconds
            max_eta = 60 # check the eta
             ## TODO: https://stackoverflow.com/questions/53315109/how-to-stop-youtube-dl-download-inside-a-thread-using-python-3

            if d["status"] == "finished":
                print("Download complete!!!")
                track.inputfile = d['filename']
                notify.put_nowait(track)
                

        # the url of the track to be downloaded, this should be populated in the query handler    
        urls = [track.URL]

        # options for ytdlp, m4a audio only and no fixup
        #   if fixup is enabled, it calls ffmpeg in another process (?) which can mess with us trying to delete the file and ffmpeg not being able to find it
        ydl_opts = {
            'format': 'bestaudio',
            'fixup': 'never',
            'outtmpl': '%(title).200B.%(ext)s' # https://github.com/yt-dlp/yt-dlp/issues/1136 for too long default filenames
            # ℹ️ See help(yt_dlp.postprocessor) for a list of available Postprocessors and their arguments or https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/YoutubeDL.py#L128-L278
        }

        # call the download
        with YoutubeDL(ydl_opts) as ydl:
            print("track URL: " + track.URL)
            ydl.add_progress_hook(dl_callback)
            error_code = ydl.download(urls)

        # await the completion

        await notify.get()
        print("download done!")

    async def order_handler(self):
        print("Order handler started")

        # loop for getting the order for the next song from the discord interface
        while True:
            order = await self.order_queue.get()  # wait on an order for the next song, like a notify mailbox
                                            # the contents of the order_queue are not relevent since
                                            # its only being used as a messaging system between coroutines
            print("new order found!")



            # free the baton for discord interface to respond
            await asyncio.sleep(0.5)

            # now a song is requested, download the next track
            
            if len(self.queue_list) > 0:    # make sure there is a song to play
                print("starting order processing")

                # get the first thing to play
                track = self.queue_list.pop(0)
                print("checking condition: ")
                res = self.song_in_pool(track)
                if res is True:
                    print("song already in pool!")
                else:
                    print("calling DL")
                    await self.download_track(track)    # request the download and wait for completion

                    await self.normalize_track(track)  # request normalizing the loudness and wait for completion

                print("DL complete, sending to player")
                await self.player_queue.put(track)
            else:
                print("order requested but list empty?")



    async def start(self):
        query_parse_task = asyncio.create_task(self.query_parser())
        order_handler_task = asyncio.create_task(self.order_handler())
        await query_parse_task
        await order_handler_task





                