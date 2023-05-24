import json
import asyncio
import TrazomDiscordInterface


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

    ## datastructure setup
    querys = asyncio.Queue(maxsize = 0)

    ##  individual module startup wrapper definitions. This lets initializations and
    #   any other setup to be done in one call for python's asynchio create_task function
    async def StartDiscord():
        discordInterface = TrazomDiscordInterface.main(token = TOKEN, guild = guild, queue = querys)
        await discordInterface.start()


    ## 

    discord_task = asyncio.create_task(StartDiscord())
    print("after start")

    await discord_task

asyncio.run(main())