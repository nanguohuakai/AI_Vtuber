import sounddevice as sd
import soundfile as sf


def play_audio(audio_path):
    data, fs = sf.read(audio_path)

    sd.play(data, fs)

    sd.wait()
