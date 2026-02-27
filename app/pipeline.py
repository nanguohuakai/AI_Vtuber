import os
from typing import Any

import requests

from app.tasks import process_song

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2:7b")
TTS_URL = os.getenv("TTS_URL", "http://localhost:9880/tts")
TTS_SPEAKER = os.getenv("TTS_SPEAKER", "default")


SONG_KEYWORDS = ("点歌", "唱", "来一首", "song")


def is_song_request(text: str) -> bool:
    return any(k in text.lower() for k in SONG_KEYWORDS)


def chat_with_llm(text: str) -> str:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": text, "stream": False},
            timeout=6,
        )
        resp.raise_for_status()
        return resp.json().get("response", "我在思考中，请再说一次。")
    except Exception:
        return "抱歉，我刚刚走神了，能再说一遍吗？"


def tts(text: str) -> str:
    try:
        resp = requests.post(
            TTS_URL,
            json={"text": text, "speaker": TTS_SPEAKER},
            timeout=8,
        )
        resp.raise_for_status()
        # 最小 demo 不做音频存储，返回占位地址
        return "file:///tmp/tts.wav"
    except Exception:
        return "file:///tmp/tts_fallback.wav"


def handle_chat_or_song(uid: int, uname: str, content: str) -> dict[str, Any]:
    if is_song_request(content):
        task = process_song.delay(uid=uid, uname=uname, query=content)
        return {"mode": "song", "task_id": task.id, "message": "点歌任务已入队"}

    reply = chat_with_llm(f"{uname} 说：{content}")
    audio_url = tts(reply)
    return {"mode": "chat", "text": reply, "audio_url": audio_url}
