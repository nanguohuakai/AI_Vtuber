# AI_Vtuber（B站）开源可部署最小方案

这个仓库提供一套**可直接扩展到商用**的 AI 主播最小骨架，目标：

- 聊天响应 ≤ 8 秒
- 点歌处理 ≤ 30 秒
- 支持 GPU 加速
- 模块可替换（本地部署 / 云 API）

## 目录结构

```text
.
├── app/
│   ├── main.py          # FastAPI 入口（弹幕/控制接口）
│   ├── pipeline.py      # 聊天链路 & 点歌任务分发
│   ├── tasks.py         # Celery 异步点歌任务
│   └── requirements.txt
├── docker-compose.yml   # Redis + 主服务 + 可替换推理服务占位
├── .env.example
└── README.md
```

## 快速启动（最小 Demo）

1. 安装依赖（本地运行）

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
```

2. 启动 Redis（本机）

```bash
redis-server
```

3. 启动 Celery worker

```bash
celery -A app.tasks worker --loglevel=info
```

4. 启动 API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 9000
```

## 接口说明

### 1) 弹幕入口

`POST /event/danmaku`

请求示例：

```json
{
  "uid": 10001,
  "uname": "观众A",
  "content": "唱一首夜曲"
}
```

返回（点歌）：

```json
{
  "mode": "song",
  "task_id": "...",
  "message": "点歌任务已入队"
}
```

返回（聊天）：

```json
{
  "mode": "chat",
  "text": "...",
  "audio_url": "file:///tmp/tts.wav"
}
```

## 组件对接建议

- 弹幕监听：`blivedm`（将监听事件转发到 `/event/danmaku`）
- LLM：默认对接 `Ollama`（`qwen2:7b`）
- TTS：默认预留 `GPT-SoVITS` HTTP 调用
- 点歌链路：`yt-dlp` -> `Demucs` -> `RVC` -> 混音
- 驱动模型：VTube Studio WebSocket API

## Docker 化

仓库提供 `docker-compose.yml` 骨架服务：

- `redis`
- `main_app`
- `llm`（Ollama）
- `tts`（GPT-SoVITS 占位）
- `rvc`（RVC 占位）

> 说明：`tts` 与 `rvc` 镜像地址需替换为你自己的可用镜像或 Dockerfile。

## 性能预算（参考）

- 聊天链路：LLM 1~2s + TTS 2~4s => 约 6s
- 点歌链路：下载+分离+转换+合成 => 约 24s（GPU）

满足目标约束：聊天 ≤ 8 秒，点歌 ≤ 30 秒。
