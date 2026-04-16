import os
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "请将你的真实API Key放入.env文件")

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
DB_PATH = "chat_history.db"
# ========================================

app = FastAPI()


# ================ 数据库初始化 ================
def init_db():
    """初始化数据库，创建 conversations 表"""
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
    """保存一条消息到数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    conn.commit()
    conn.close()


def get_history(session_id: str, limit: int = 10):
    """获取某个会话最近 N 条消息"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
        (session_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]


# ================ 请求/响应模型 ================
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


# ================ API 接口 ================
@app.get("/")
async def root():
    return {"message": "AI 服务已启动，请使用 POST 请求访问 /chat"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话接口，支持多轮对话"""
    # 如果没有传 session_id，自动生成一个
    session_id = request.session_id or str(uuid.uuid4())

    # 保存用户消息
    save_message(session_id, "user", request.message)

    # 获取最近 10 条历史
    history = get_history(session_id, limit=10)

    # 构建 messages
    messages = history + [{"role": "user", "content": request.message}]

    # 调用 DeepSeek API
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        reply = result["choices"][0]["message"]["content"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调用 AI API 失败: {str(e)}")

    # 保存 AI 回复
    save_message(session_id, "assistant", reply)

    return ChatResponse(reply=reply, session_id=session_id)


@app.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """获取某个会话的所有历史记录"""
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
        "messages": [
            {"role": row[0], "content": row[1], "time": row[2]}
            for row in rows
        ]
    }


# ================ 启动服务 ================
if __name__ == "__main__":
    import uvicorn
    init_db()  # 启动时初始化数据库
    uvicorn.run(app, host="0.0.0.0", port=8000)