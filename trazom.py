import json
import asyncio
import TrazomDiscordInterface
import queryHandler


##  The main function for the entire Trazom Music Bot
#   this is declared as an async function to be able to await all the
#   submodules associated with the bot.
#       Discord interface (discord.py)
#       string parse to mp3 (youtube, spotify, ffmpeg)
#       song database and library handler
#       song player
async def main():

    ## Loading config json where token is the bot's api token and guild is the server to be run on
    config = json.load(open("myConfig.json"))
    TOKEN = config["token"]
    guild = config["guild"]
    cid = config["spotify_client_ID"]
    secret = config["spotify_app_secret"]

    ## datastructure setup
    querys = asyncio.Queue(maxsize = 0)
    player_queue = asyncio.Queue(maxsize = 2)
    order_queue = asyncio.Queue(maxsize = 1)

    ##  individual module startup wrapper definitions. This lets initializations and
    #   any other setup to be done in one call for python's asynchio create_task function
    async def StartDiscord():
        discordInterface = TrazomDiscordInterface.main(token = TOKEN, guild = guild, query_queue = querys, player_queue = player_queue, order_queue = order_queue)
        await discordInterface.start()

    async def StartQueryHandler():
        query_handler = queryHandler.main(cid, secret, querys, player_queue, order_queue)
        await query_handler.start()


    ## 

    discord_task = asyncio.create_task(StartDiscord())
    query_task = asyncio.create_task(StartQueryHandler())
    print("after start")

    await discord_task
    await query_task

## starting point of the bot
asyncio.run(main())