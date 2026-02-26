import os
import subprocess

import config


def download_song(song_name):
    output = os.path.join(config.SONG_DIR, song_name + ".mp3")

    if os.path.exists(output):
        return output

    cmd = [
        "yt-dlp",
        "ytsearch1:" + song_name,
        "-x",
        "--audio-format",
        "mp3",
        "-o",
        output,
    ]

    subprocess.run(cmd)

    return output
