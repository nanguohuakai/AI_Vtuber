import os
import subprocess

import config


def separate_vocals(song_path):
    output = os.path.join(config.OUTPUT_DIR, "vocals.wav")

    cmd = [
        "python",
        config.UVR_SCRIPT,
        "--input",
        song_path,
        "--output",
        output,
    ]

    subprocess.run(cmd)

    return output
