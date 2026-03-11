import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

CLAUDE_URL = "https://claude.ai/new"
CDP_ENDPOINT = "http://127.0.0.1:9222"
MODEL_COOKIE_PATH = Path("data/model_cookies.json")

app = FastAPI(title="Claude Web OpenAI Gateway", version="0.2.0")


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "claude-web"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class GatewayState:
    playwright: Any = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    lock: asyncio.Lock = asyncio.Lock()
    cookies_by_model: dict[str, list[dict[str, Any]]] = {}


state = GatewayState()


def _build_prompt(messages: list[ChatMessage]) -> str:
    merged: list[str] = []
    for msg in messages:
        merged.append(f"[{msg.role}] {msg.content}")
    return "\n".join(merged)


def _load_model_cookies() -> dict[str, list[dict[str, Any]]]:
    if not MODEL_COOKIE_PATH.exists():
        return {}

    raw = json.loads(MODEL_COOKIE_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"{MODEL_COOKIE_PATH} 内容格式错误，应为 JSON 对象")

    cookies_by_model: dict[str, list[dict[str, Any]]] = {}
    for model, payload in raw.items():
        if isinstance(payload, dict):
            cookies = payload.get("cookies", [])
        else:
            cookies = payload

        if not isinstance(model, str) or not isinstance(cookies, list):
            continue
        cookies_by_model[model] = cookies

    return cookies_by_model


async def _apply_model_cookies(context: BrowserContext, model: str) -> None:
    cookies = state.cookies_by_model.get(model)
    if cookies is None:
        if state.cookies_by_model:
            supported = ", ".join(sorted(state.cookies_by_model))
            raise HTTPException(status_code=400, detail=f"不支持的 model: {model}。可用 model: {supported}")
        return

    if cookies:
        await context.clear_cookies()
        await context.add_cookies(cookies)


async def _ensure_page(model: str) -> Page:
    state.cookies_by_model = state.cookies_by_model or _load_model_cookies()

    if state.page and not state.page.is_closed() and state.context:
        await _apply_model_cookies(state.context, model)
        return state.page

    state.playwright = state.playwright or await async_playwright().start()
    state.browser = await state.playwright.chromium.connect_over_cdp(CDP_ENDPOINT)

    if state.browser.contexts:
        state.context = state.browser.contexts[0]
    else:
        state.context = await state.browser.new_context()

    await _apply_model_cookies(state.context, model)

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


@app.on_event("shutdown")
async def _shutdown() -> None:
    if state.browser:
        await state.browser.close()
    if state.playwright:
        await state.playwright.stop()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest) -> dict[str, Any]:
    if req.stream:
        raise HTTPException(status_code=400, detail="当前仅支持 stream=false")

    user_messages = [m for m in req.messages if m.role in {"system", "user"}]
    if not user_messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    prompt = _build_prompt(user_messages)

    async with state.lock:
        page = await _ensure_page(req.model)
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
