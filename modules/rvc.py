import os
import subprocess

import config


def rvc_convert(input_path):
    output = os.path.join(config.OUTPUT_DIR, "converted.wav")

    cmd = [
        "python",
        config.RVC_SCRIPT,
        "--input",
        input_path,
        "--output",
        output,
        "--model",
        config.RVC_MODEL_PATH,
        "--device",
        "cuda",
    ]

    subprocess.run(cmd)

    return output
