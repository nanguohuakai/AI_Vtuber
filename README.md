# Claude Web OpenAI-Compatible Gateway

这个项目提供了一个 **OpenAI 格式** 的 API 网关，底层通过连接本地 Chrome 的 **Remote Debugging (CDP)** 会话，驱动已登录的 `https://claude.ai/new` 页面来完成请求。

> 适用场景：你希望保留 Claude 网页登录态（账号、会话、权限），同时在外部用 OpenAI SDK/HTTP 方式调用。

## 1. 启动 Chrome 调试模式

先关闭所有 Chrome 进程，然后执行：

```bash
./scripts/start_chrome_debug.sh
```

该脚本会：
- 使用独立用户目录 `./.chrome-profile`
- 开启 `--remote-debugging-port=9222`
- 打开 `https://claude.ai/new`

首次启动后，请在浏览器里手动完成 Claude 登录。

## 2. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 3. 执行 Onboard，保存 model 对应 Cookie

```bash
./scripts/onboard.sh claude-web
```

或交互式输入多个模型（例如 `claude-web,claude-3-7-sonnet`）。脚本会：
- 连接 `http://127.0.0.1:9222`
- 从当前调试浏览器读取 `https://claude.ai` 的 cookie
- 写入 `data/model_cookies.json`

当 `model_cookies.json` 中存在条目时，API 仅允许请求这些 model，并在请求前注入对应 cookie。

## 4. 启动 API 服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 5. OpenAI 兼容调用示例

### cURL

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "claude-web",
    "messages": [
      {"role": "user", "content": "请用一句话介绍你自己"}
    ],
    "stream": false
  }'
```

### Python(OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="dummy")

resp = client.chat.completions.create(
    model="claude-web",
    messages=[{"role": "user", "content": "你好，帮我总结一下今天待办"}],
)
print(resp.choices[0].message.content)
```

## 已知限制

- 这是网页自动化方案，不是 Claude 官方 API，页面变更可能导致失效。
- 若页面未登录、出现风控、人机验证，会导致请求失败。
- 并发能力有限，默认串行请求（一个浏览器标签处理一个请求）。
