import asyncio
import time
import uuid
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

CLAUDE_URL = "https://claude.ai/new"
CDP_ENDPOINT = "http://127.0.0.1:9222"

app = FastAPI(title="Claude Web OpenAI Gateway", version="0.1.0")


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "claude-web"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class SessionExportRequest(BaseModel):
    url: str = CLAUDE_URL
    include_local_storage: bool = True


def _domain_matches(cookie_domain: str, host: str) -> bool:
    normalized = cookie_domain.lstrip(".").lower()
    host = host.lower()
    return host == normalized or host.endswith(f".{normalized}")


class GatewayState:
    playwright: Any = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    lock: asyncio.Lock = asyncio.Lock()


state = GatewayState()


def _build_prompt(messages: list[ChatMessage]) -> str:
    merged: list[str] = []
    for msg in messages:
        merged.append(f"[{msg.role}] {msg.content}")
    return "\n".join(merged)


async def _ensure_page() -> Page:
    if state.page and not state.page.is_closed():
        return state.page

    state.playwright = state.playwright or await async_playwright().start()
    state.browser = await state.playwright.chromium.connect_over_cdp(CDP_ENDPOINT)

    if state.browser.contexts:
        state.context = state.browser.contexts[0]
    else:
        state.context = await state.browser.new_context()

    pages = state.context.pages
    if pages:
        state.page = pages[0]
    else:
        state.page = await state.context.new_page()

    await state.page.goto(CLAUDE_URL, wait_until="domcontentloaded")
    return state.page


async def _send_and_read(page: Page, prompt: str) -> str:
    input_selector = 'div[contenteditable="true"]'

    try:
        await page.wait_for_selector(input_selector, timeout=15000)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Claude 页面未就绪。请确认已登录并且页面可用。",
        ) from exc

    assistant_before = await page.locator('[data-is-streaming], div[data-testid="message-assistant"]').count()

    await page.locator(input_selector).first.click()
    await page.keyboard.type(prompt)
    await page.keyboard.press("Enter")

    deadline = time.time() + 120
    last_text = ""
    stable_count = 0

    while time.time() < deadline:
        await page.wait_for_timeout(1000)
        responses = page.locator('div[data-testid="message-assistant"]')
        total = await responses.count()

        if total <= assistant_before:
            continue

        latest = responses.nth(total - 1)
        text = (await latest.inner_text()).strip()

        if not text:
            continue

        if text == last_text:
            stable_count += 1
        else:
            last_text = text
            stable_count = 0

        streaming = await page.locator('[data-is-streaming="true"]').count()
        if streaming == 0 and stable_count >= 2:
            return text

    raise HTTPException(status_code=504, detail="等待 Claude 响应超时")


async def _collect_session_data(url: str, include_local_storage: bool) -> dict[str, Any]:
    page = await _ensure_page()
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(status_code=400, detail="url 必须是合法的 http(s) 地址")

    host = parsed.hostname or ""
    cookies = await state.context.cookies() if state.context else []
    matched_cookies = [c for c in cookies if _domain_matches(c.get("domain", ""), host)]

    local_storage: dict[str, str] = {}
    if include_local_storage:
        await page.goto(url, wait_until="domcontentloaded")
        local_storage = await page.evaluate(
            """() => {
                const data = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const k = localStorage.key(i);
                    data[k] = localStorage.getItem(k);
                }
                return data;
            }"""
        )

    return {
        "url": url,
        "cookie_count": len(matched_cookies),
        "cookies": matched_cookies,
        "local_storage": local_storage,
        "logged_in": len(matched_cookies) > 0,
        "exported_at": int(time.time()),
    }


@app.on_event("shutdown")
async def _shutdown() -> None:
    if state.browser:
        await state.browser.close()
    if state.playwright:
        await state.playwright.stop()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/session/status")
async def session_status(url: str = CLAUDE_URL) -> dict[str, Any]:
    async with state.lock:
        session = await _collect_session_data(url=url, include_local_storage=False)

    return {
        "status": "ok",
        "url": session["url"],
        "logged_in": session["logged_in"],
        "cookie_count": session["cookie_count"],
        "exported_at": session["exported_at"],
    }


@app.post("/v1/session/export")
async def session_export(req: SessionExportRequest) -> dict[str, Any]:
    async with state.lock:
        return await _collect_session_data(
            url=req.url,
            include_local_storage=req.include_local_storage,
        )


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest) -> dict[str, Any]:
    if req.stream:
        raise HTTPException(status_code=400, detail="当前仅支持 stream=false")

    user_messages = [m for m in req.messages if m.role in {"system", "user"}]
    if not user_messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    prompt = _build_prompt(user_messages)

    async with state.lock:
        page = await _ensure_page()
        output = await _send_and_read(page, prompt)

    now = int(time.time())
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": now,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": output,
                },
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }
