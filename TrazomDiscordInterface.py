import discord
from asyncio import Queue
from discord import app_commands
import os
import asyncio
from data_structures import Track
from data_structures import QueryItem


##  an override / child class of the default discord Client
#   Following the discord.py example code, this is done to
#   be able to sync to the server in the setup hook but in practice,
#   I found that I had to call the sync in the on_ready for the
#   right commands to be displayed in the actual text channels (the
#   server settings showed the right ones)
class MyClient(discord.Client):

    #   storing data structures inside the class since I am defining
    #   commands inside the setup hook. Unsure if this has any negative
    #   effects
    def __init__(self, *, intents: discord.Intents, guild, query_queue: Queue, player_queue: Queue, order_queue: Queue):
        super().__init__(intents = intents)
        self.tree = app_commands.CommandTree(self)
        self.myguild = guild
        self.queryq = query_queue
        self.player_queue = player_queue
        self.order_queue = order_queue
        self.vchannel = None
        self.player_track = None
        
    async def music_player(self):
        
        next_trigger = Queue(1)
        print("initialized size: " + str(next_trigger.qsize()))

        # callback function for AFTER a stream is exhausted
        # but effectively is called right after the track starts
        # since the stream is read very quickly but takes human time
        # to play back
        def on_track_start(track):
            print("Player Finish Called by tid: " + str(track.track_id))
           # next_trigger.put_nowait(track)
            #self.order_queue.put_nowait("item")

        # async handler for ordering the next song to play when the current
        # one is finished playing
        async def next_track_handler():
            while True:
                print("next handler initialized")

                print("next handler start size: " + str(next_trigger.qsize()))
                track = await next_trigger.get()
                print("next handler item got!")

                while True: # poll for the song end / skip
                    await asyncio.sleep(1)
                    if self.voice_clients[0].is_playing():
                        continue # continue waiting
                    else:
                        print("tid self: " + str(track.track_id) + " current: " + str(self.player_track))
                        if track.track_id == self.player_track:
                            print("normal skip")
                            self.order_queue.put_nowait("item")
                        else:
                            print("override skip")
                        break


        async def player_handler():
            while True:
                track:Track = await self.player_queue.get()
                self.player_track = track.track_id
                if self.vchannel is None: # clear the queue
                    self.order_queue.put_nowait("item")
                    continue

                print("player: order ready")
                source = discord.FFmpegOpusAudio(track.filepath)
                print("Source: ")
                print(source)

                # check if something is already playing
                if self.voice_clients[0].is_playing():
                    print("something already playing")
                    self.voice_clients[0].stop()
                self.voice_clients[0].play(source, after = on_track_start(track))
                await next_trigger.put(track)
                print("now playing " + track.title)
        
        next_handler_task = asyncio.create_task(next_track_handler())
        player_handler_task = asyncio.create_task(player_handler())

        await next_handler_task
        await player_handler_task
        
    # listener override / piggyback to auto-disconnect
    async def on_voice_state_update(self, member, before, after):
        print("change detected")

        if self.vchannel is None: # we aren't in any VCs
            return
        
        print("members: " + str(len(self.vchannel.members)))

        if len(self.vchannel.members) == 1: # are we the only ones here

            if len(self.voice_clients) > 0: # sanity check that we have connections
                for connection in self.voice_clients:
                    self.vchannel = None
                    await connection.disconnect()
                return

        # otherwise proceed as normal
        return

    async def setup_hook(self):

        @self.tree.command(name = "print", description = "parrot back") 
        async def first_command(interaction):
            files = [f for f in os.listdir(os.path.join('.','songPool'))]
            for f in files:
                fpath = os.path.abspath(os.path.join('songPool',f))
                print("fpath: " + fpath + " of len " + str(os.path.getsize(fpath)))
            await interaction.response.send_message("test")

        @self.tree.command(name = "sim", description = "simulate a order queue") 
        async def test2(interaction):
            self.order_queue.put_nowait("holderitem")
            await interaction.response.send_message("Order being sent")



        @self.tree.command(name = "p", description = "youtube lookup") 
        async def query(interaction: discord.Interaction, request: str):

            ## handle joining a voice channel
            print(interaction.user.voice)
            # make sure user is in a VC
            if interaction.user.voice is None or interaction.user.voice.channel is None:
                print("not in VC")
                await interaction.response.send_message("You must be in a Voice Channel~")
                return
            
            # are we in a vc?
            if self.vchannel is None: # then we join the user's channel
                self.vchannel = interaction.user.voice.channel
                await self.vchannel.connect()
                

            # is the user in our VC?
            
            new_query = QueryItem(request, interaction)
            response_msg = "placed " + request + " into lookup queue"
            self.queryq.put_nowait(new_query)
            await interaction.response.send_message(response_msg)

##  Main function / class for the discord interface module. This consists of
#   two submodules, the input interface and the discord voice interface.
#   In practice the input submodule is fully implemented in commands while
#   the voice interface will be more integrated with the library / player module
class main:

    def __init__(self, token, guild, query_queue: Queue, player_queue: Queue, order_queue: Queue):
        self.token = token
        self.guild = discord.Object(id = guild)
        self.intents = discord.Intents.default()
        self.client = MyClient(intents = self.intents, guild = self.guild, query_queue = query_queue, player_queue = player_queue, order_queue = order_queue)


    ## starts the discord client and does the syncing in the on_ready event
    async def start(self):

        client = self.client
        # run at the end of this function

        @client.event
        async def on_ready():
            #self.tree.copy_global_to(guild=self.myguild)
            await client.tree.sync()
            print("Ready!")

        

        #   client.start is used instead of run (like in many examples) to hook into
        #   the pre-existing async loop instead of setting one up itself, so start
        #   is non blocking and await is used to block until its finished instead

        client_task = asyncio.create_task(self.client.start(token = self.token))
        print("player task started")
        player_task = asyncio.create_task(self.client.music_player())

        await client_task
        await player_task

