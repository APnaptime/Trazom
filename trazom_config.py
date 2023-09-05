
spotify_client_ID = ""
spotify_app_secret = ""

norm_folder = "norm_cache"            # folder that caches normalized tracks
norm_allocated = 240 * 1000000      # how much space is allocated to the folder for normalized tracks in bytes
norm_clear = 40 * 1000000           # how much space to try keep empty for a new song in the norm folder
                                    # a good option is the max song size you'd expect in bytes

dl_folder = "download_cache"          # folder that caches downloaded tracks
dl_allocated = 50 * 1000000      # how much space is allocated to the folder for downloaded tracks in bytes
dl_clear = 5 * 1000000           # how much space to try keep empty for a new song in the download folder
                                    # a good option is the max song size you'd expect to download in bytes

                                    # clear must be less than allocated for both folders

download_wait_after_fetch = 5   # how long to wait for a download to finish
                                # after the track has been fetched

base_volume = .15             # the base volume of the bot 0-1 -Reccomended: .15

sleep_frequency = 1             # frequency to poll at when sleeping to wait for things
handoff_sleep_time = 1          # how long to sleep for when handing off the co-routine baton

reply_default_lifespan = 8      # how long to wait before deleting trazom's extraneous responses, if negative then it won't delete them

initial_song_wait = 20          # how long to wait for the first song in a session to be normalized before resorting to a download
default_song_wait = 5           # how long to wait for a song to be normalized after its required by the player before resorting to a download

q_disp_title_max_char = 40      # how many characters to display for a song title in the queue
q_disp_max_tracks = 12          # how many tracks to display in the queue
