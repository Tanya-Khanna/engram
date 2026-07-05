"""Proof of Alibaba Cloud deployment — Engram backend.
Runs on Alibaba Cloud ECS (Singapore), calls Qwen via DashScope."""
import os, socket, datetime
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)
r = client.chat.completions.create(
    model="qwen3.7-plus",
    messages=[{"role": "user", "content": "Say: Engram backend live on Alibaba Cloud ECS."}],
)
print(datetime.datetime.utcnow().isoformat(), socket.gethostname())
print(r.choices[0].message.content)
