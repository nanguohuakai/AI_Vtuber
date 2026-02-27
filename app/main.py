from fastapi import FastAPI
from pydantic import BaseModel

from app.pipeline import handle_chat_or_song

app = FastAPI(title="AI_Vtuber Demo API", version="0.1.0")


class DanmakuEvent(BaseModel):
    uid: int
    uname: str
    content: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/event/danmaku")
def on_danmaku(event: DanmakuEvent) -> dict:
    return handle_chat_or_song(event.uid, event.uname, event.content)
