import os
import sqlite3
import uuid
import importlib
import pkgutil
from typing import Optional, List, Dict, Any
import logging
import time

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ================ 配置 ================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
DB_PATH = "chat_history.db"

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
request_count=0

# ================ 数据库 ================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_message(session_id: str, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    conn.commit()
    conn.close()

def get_history(session_id: str, limit: int = 10) -> List[Dict[str, str]]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
        (session_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]

# ================ Skill 动态加载 ================
import skills

def load_skills():
    skill_definitions = []
    skill_executors = {}
    for finder, name, ispkg in pkgutil.iter_modules(skills.__path__):
        module = importlib.import_module(f"skills.{name}")
        if hasattr(module, "get_skill_definition") and hasattr(module, "execute"):
            skill_definitions.append(module.get_skill_definition())
            skill_executors[name] = module.execute
    return skill_definitions, skill_executors

SKILL_DEFINITIONS, SKILL_EXECUTORS = load_skills()

# ================ 请求/响应模型 ================
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    session_id: str

# ================ API 接口 ================
@app.get("/")

@app.get("/metrics")
async def metrics():
    return {"requests_total": request_count}

@app.get("/ping")
async def ping():
    global request_count
    request_count += 1
    logger.info(f"Received request to/ping,total count:{request_count}")
    return {"message": "pong"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/metrics")
async def metrics():
    return {"requests_total": 1}
async def root():
    return {"message": "AI 服务已启动，请使用 POST 请求访问 /chat"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start_time = time.time()
    logger.info(f"Request start - session_id={request.session_id}, message={request.message[:50]}")
    session_id = request.session_id or str(uuid.uuid4())
    save_message(session_id, "user", request.message)

    history = get_history(session_id, limit=10)
    messages = history + [{"role": "user", "content": request.message}]

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": [{"type": "function", "function": func} for func in SKILL_DEFINITIONS],
        "tool_choice": "auto"
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        message = result["choices"][0]["message"]

        if message.get("tool_calls"):
            tool_call = message["tool_calls"][0]
            func_name = tool_call["function"]["name"]
            import json
            arguments = json.loads(tool_call["function"]["arguments"])
            # 找到对应的 executor
            executor = None
            for name, exec_func in SKILL_EXECUTORS.items():
                module = importlib.import_module(f"skills.{name}")
                if hasattr(module, "SKILL_NAME") and module.SKILL_NAME == func_name:
                    executor = exec_func
                    break
            if executor:
                logger.info(f"Calling skill: {func_name} with args: {arguments}")
                tool_result = executor(**arguments)
                logger.info(f"Skill result: {tool_result[:100]}")
                messages.append(message)  # assistant 的 tool_calls 消息
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": tool_result
                })
                payload2 = {
                    "model": MODEL,
                    "messages": messages
                }
                response2 = requests.post(API_URL, headers=headers, json=payload2, timeout=30)
                response2.raise_for_status()
                final_reply = response2.json()["choices"][0]["message"]["content"]
                save_message(session_id, "assistant", final_reply)
                return ChatResponse(reply=final_reply, session_id=session_id)
            else:
                reply = "抱歉，无法执行该工具。"
        else:
            reply = message["content"]

        save_message(session_id, "assistant", reply)
        elapsed = time.time() - start_time
        logger.info(f"Request end - session_id={session_id}, elapsed={elapsed:.2f}s")
        return ChatResponse(reply=reply, session_id=session_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调用 AI API 失败: {str(e)}")

@app.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content, created_at FROM conversations WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return {
        "session_id": session_id,
        "messages": [{"role": r[0], "content": r[1], "time": r[2]} for r in rows]
    }

if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)