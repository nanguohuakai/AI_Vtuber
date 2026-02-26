from modules.downloader import download_song
from modules.separator import separate_vocals
from modules.rvc import rvc_convert
from modules.player import play_audio


def auto_sing(song_name):
    print(f"\n[1] Downloading: {song_name}")
    song_path = download_song(song_name)

    print("[2] Separating vocals...")
    vocals_path = separate_vocals(song_path)

    print("[3] Converting voice...")
    converted_path = rvc_convert(vocals_path)

    print("[4] Playing...")
    play_audio(converted_path)

    print("[Done]\n")


def main():
    print("=== AI Vtuber Auto Singer ===")

    while True:
        song = input("点歌 > ")

        if song.strip() == "":
            continue

        auto_sing(song)


if __name__ == "__main__":
    main()
