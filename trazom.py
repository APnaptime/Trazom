import json
import asyncio
import subprocess
import os

import nextcord
import spotipy

from spotipy.oauth2 import SpotifyClientCredentials

import trazom_config
import trazom_utils

from trazom_utils import Track
from trazom_utils import QueryItem
from trazom_utils import PlayQueue



class Trazom():
    
    def __init__(self, interaction: nextcord.Interaction):

        # spotify
        self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=trazom_config.spotify_client_ID, client_secret=trazom_config.spotify_app_secret))

        # queues for handleing inter-routine data
        self.player_queue = asyncio.Queue(maxsize = 2)  # downloaded tracks to be played by the player
        self.order_queue = asyncio.Queue(maxsize = 1)   # requests to download  processed query
        self.next_queue = asyncio.Queue(maxsize = 1)   # queue to handle listening for a song's end, num songs in = num songs to wait for
        self.query_queue = asyncio.Queue()

        self.track_queue = PlayQueue()                      # the player queue for processed tracks to be played, allows for custom sorting (vs default asyncio.Queue)
        self.vchannel = interaction.user.voice.channel      # channel to connect to, note this is not a connection yet
        self.tasks = None                                   # asyncio tasks trazom uses, to be canceled upon request or unload
        self.now_playing = None                             # the currently playing song
        self.q_msg = None
        self.trazom_channel = interaction.channel
    
        if not os.path.exists(os.path.join(os.getcwd(), trazom_config.norm_folder)):
            os.makedirs(os.path.join(os.getcwd(), trazom_config.norm_folder))
        
        if not os.path.exists(os.path.join(os.getcwd(), trazom_config.dl_folder)):
            os.makedirs(os.path.join(os.getcwd(), trazom_config.dl_folder))


    # coroutine for ordering the next song to play when the current one is finished playing
    async def next_track_handler(self):

        while True:
            track = await self.next_queue.get()
            time_elapsed = 0
            while True: # poll for the song end / skip
                await asyncio.sleep(trazom_config.sleep_frequency)
                time_elapsed = time_elapsed + trazom_config.sleep_frequency

                if self.voice_client.is_playing():
                    continue # continue waiting
                else:
                    self.now_playing = None

                    if self.q_msg is not None:
                        await self.q_msg.edit(embed = self.track_queue.get_embed(self.now_playing))

                    self.order_queue.put_nowait(trazom_config.default_song_wait)

                    if time_elapsed < track.duration: # if we finish ahead of time (skip manually stops the track)
                        # record the amount of time skipped for the order calculations
                        self.track_queue.notify_skipped(track = track, duration = track.duration - time_elapsed)

                    break



    # coroutine player that interfaces with the discord voice client
    async def player_handler(self):

        while True:
            track:Track = await self.player_queue.get()
            self.player_track = track.track_id

            source = nextcord.FFmpegOpusAudio(track.play_file)

            if self.voice_client.is_playing():
                self.voice_client.stop()

            self.now_playing = track

            if self.q_msg is not None:
                await self.q_msg.edit(embed = self.track_queue.get_embed(self.now_playing))

            self.voice_client.play(source)
            trazom_utils.update_access_time(track)
            await self.next_queue.put(track)
            
    # coroutine that parses string searches into track datastructures with spotipy and yt-dlp
    async def query_handler(self):

        while True:
            queryItem = await self.query_queue.get()

            # handoff to let response happen
            await asyncio.sleep(trazom_config.handoff_sleep_time)

            if "open.spotify.com" in queryItem.query:       # if its a spotify link
                try:
                    components = queryItem.query.split("/")         # manual spotify url processing
                    link_type = components[-2]                      # detect type from url
                    spotify_id = (components[-1].split("?"))[0]     # extract ID
                    tracks = []                                     # song names from the spotify link

                    if link_type == "playlist": # playlist of tracks
                        result = self.sp.playlist(spotify_id)
                        for item in result['tracks']['items']:
                            tracks.append(item['track']['name'] + " " + item['track']['artists'][0]['name'])    # for every song, youtube search: trackname + track artist

                    elif link_type == "album":  # album, unlike playlists, no need to ['track']
                        result = self.sp.album(spotify_id)
                        for item in result['tracks']['items']:
                            tracks.append(item['name'] + " " + item['artists'][0]['name'])    # for every song, youtube search: trackname + track artist

                    elif link_type == "track":  # case single track
                        result = self.sp.track(spotify_id)
                        tracks.append(result['name'] + " " + result['artists'][0]['name'])  # youtube search: trackname + track artist

                    # now for every track that was found, perform a youtube search

                    for track_query in tracks:
                        await asyncio.sleep(trazom_config.handoff_sleep_time)   # search can be expensive so we pass off before
                        songs = trazom_utils.search(track_query)                # perform the search on tracks[]
                  
                        for song in songs:
                            self.track_queue.put(Track(song, queryItem.user, queryItem.id))
                        
                except:
                    print("ERROR: parsing spotify query: " + queryItem.query)
                    return
            
            else:                                                   # youtube search string / url
                songs = trazom_utils.search(queryItem.query)
                for song in songs:
                    self.track_queue.put(Track(song, queryItem.user, queryItem.id))
                
            # after we've inserted into the track_queue, now update the embed
            if self.q_msg is not None:
                await self.q_msg.edit(embed = self.track_queue.get_embed(self.now_playing))

    # coroutine that provides downloaded (and normalized) songs to the player via queue
    async def order_handler(self):
        # put in an order so we start playing immedietely
        self.order_queue.put_nowait(trazom_config.initial_song_wait)

        # loop for getting the order for the next song from the discord interface
        while True:
            wait_duration = await self.order_queue.get()    # wait on an order for the next song, like a notify mailbox
                                                            # the contents of the order_queue are how long we should wait
                                                            # for a song to finish processing before we skip or use a downloaded version

            # now a song is requested, get the next track to be played
            track = await self.track_queue.get()
            fname = await track.fetch_track(wait_duration)

            if fname is None:
                print("trazom - order handler: fetch was none")
                continue

            await self.player_queue.put(track)


    async def start_tasks(self):
        # connect to the voice channel
        self.voice_client = await self.vchannel.connect()

        # tasks for trazom
        self.tasks = [
            asyncio.create_task(self.next_track_handler(), name = "next_handler"),
            asyncio.create_task(self.player_handler(), name = "player_handler"),
            asyncio.create_task(self.order_handler(), name = "order_handler"),
            asyncio.create_task(self.query_handler(), name = "query_handler")
        ]

        # wait for them to cancel
        for task in self.tasks:
            try:
                await task
            except:
                print(task.get_name() + " cancelled!")

        # all tasks cancelled
        print("trazom tasks collected!")
        await self.voice_client.disconnect()

        if self.q_msg is not None:
            await self.q_msg.edit(embed = self.track_queue.get_session_summary())


    # non async wrapper function for starting the music bot
    def start(self):
        # call the async functions required to start the bot
        self.task = asyncio.create_task(self.start_tasks())


    
    # adds a song request (yt url, spotify url, string search) to be played
    async def play(self, interaction: nextcord.Interaction, query: str):

        queryItem = QueryItem(query, interaction)
        self.query_queue.put_nowait(queryItem)

        if self.q_msg is None: # if we don't already have a queue up, display one
            self.q_msg = await self.trazom_channel.send(embed = self.track_queue.get_embed(self.now_playing))
            await trazom_utils.short_response(interaction = interaction, response = ":dolphin: DON'T PANIC - the first one might take a while | `" + query + "`", delay = 20)
        else:
            await trazom_utils.short_response(interaction = interaction, response = "Searching for: `" + query + "`")
            

        


    # gets the list representation of the current play queue
    async def get_queue(self, interaction: nextcord.Interaction):

        if self.q_msg is not None:
            await self.q_msg.delete()

        self.q_msg = await self.trazom_channel.send(embed = self.track_queue.get_embed(self.now_playing))

        await trazom_utils.short_response(interaction = interaction, response = "Queue Fetched!")
    


    # orders a new song to be played or current one to stop if there is no songs left
    async def skip(self, interaction: nextcord.Interaction):

        if self.now_playing is None:
            await trazom_utils.short_response(interaction = interaction, response = ":notes: Nothing currently playing~")
        else:
            self.voice_client.stop()
            await trazom_utils.short_response(interaction = interaction, response = ":notes: Skipping " + self.now_playing.title)



    # removes the track at a given index from the play queue
    async def remove_track(self, interaction: nextcord.Interaction, track_index: int):

        removed = await self.track_queue.remove(track_index - 1)

        if removed is None: # if nothing was removed (index out of bound or something else)
            await trazom_utils.short_response(interaction = interaction, response = ":notes: Song not found!")

        else:   # otherwise, tell them of success and update the displayed queue if there is one

            if self.q_msg is not None:
                await self.q_msg.edit(embed = self.track_queue.get_embed(self.now_playing))

            await trazom_utils.short_response(interaction = interaction, response = ":notes: Removed " + removed.title)



    # stops the bot
    def stop(self):
        if self.tasks is None:
            return
        for task in self.tasks:
            print("trazom: cancel " + str(task.cancel()))
        
