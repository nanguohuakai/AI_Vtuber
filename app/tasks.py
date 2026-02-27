import os
import subprocess

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)


@app.task(bind=True, soft_time_limit=25, time_limit=30)
def process_song(self, uid: int, uname: str, query: str) -> dict:
    # 这里只是最小骨架，真实项目中请替换为：
    # 1) 下载音频（yt-dlp）
    # 2) 人声分离（demucs）
    # 3) 音色转换（rvc api）
    # 4) 混音/回放
    subprocess.run(["/bin/echo", f"song-request from {uid}:{uname} => {query}"], check=True)
    return {"ok": True, "uid": uid, "uname": uname, "query": query}
