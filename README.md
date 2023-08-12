# Trazom
niche discord music bot in a Cog

dependancies:
 - python (Tested w/ 3.9.7)
 - yt-dlp
 - nextcord (Tested w/ 2.5.0)
 - nextcord voice (pip is nextcord\[voice\])
 - spotipy

You will need (I think)
 - A working discord bot that can load extensions
 - Spotify Developer Credentials (client ID and app secret)

cool things:
 - Audio normalization with ffmpeg-normalize
 - Spotify and youtube link compatible
 - search for queries on youtube
 - time based priority queue for added "mom said its my turn"ness
 - cache files with soft folder size limits set in the config

To Do List:
 - seeded reccomendations for autoqueue

Would be nice list:
 - faster youtube searching (or at least on a subprocess)
 - queue shuffling / more sorting options

How it works:
Trazom is heavily co-routinified with 4 primary tasks. Asyncio queues (and similar) are used to
communicate and transfer work orders between the tasks. Starting with the user, when a command to play a song is input, an async function is called by something outside the trazom instance. This function puts the string and some metadata regarding the user who did the search into an asyncio queue.

One of the primary tasks: the query handler loops and waits on getting queries from that queue. The query handler mainly processes string queries from that query_queue and converts them into an internal Track datastructure that represents a single song instance. The query handler then puts those tracks into another asyncio queue like data structure (with added sorting and printout functionality) called the track_queue.

The track_queue is pulled on by a primary task: the order_handler in it's main loop. In addition to pulling a track from the track_queue, the order_handler also pulls / waits on a order_queue which acts as a signaling mailbox indicating when the order_handler should prepare the next track. This is important because the order handler's primary job is to ensure the track 
datastructure is processed from the internal representation into files in directories and since our desired behavior is to only process the next few songs in the queue instead of all of them, the order handler has to wait on both the track_queue and the order_queue. After a song is fully processed by the order handler, it is put into the player_queue where everything put into the player queue is going to be played immedietly by the player_handler task

The player_handler is one of the primary tasks and it interfaces with the discord voice client, handling the actual playing / streaming of a track to a voice channel. The main loop of the player_handler task pulls from the player_queue and plays the recieved track. Since there is no throttleing for ensuring a track plays to completion inside the player_handler, Trazom relies on regulating how items are inserted into the order_queue from the previous task.

Items are inserted into the order_queue by the next_handler (short for next track handler). In it's main loop, it passively polls the discord voice client at a set interval. When it detects that nothing is currently playing (this happens when a track natuarally plays its course or is manually stopped, by a skip command for instance) it sends an order to the order_queue, representing a "next track" request. To ensure that only one next track request is sent per one track finishing, the polling behavior is only executed once per item pulled from another queue: the next_queue. Every time the player_handler from the previous section starts playing a track, it also puts in one item into the next_queue. The end result is that for every track played, only one new order is put in. To bootstrap the process, the bot starts with an order already inside the order_queue. 