import os
import sqlite3
import uuid
import importlib
import pkgutil
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ================ 配置区域 ================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "请设置环境变量")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
DB_PATH = "chat_history.db"
# =========================================

app = FastAPI()


# ================ 数据库操作 ================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS conversations
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       session_id
                       TEXT
                       NOT
                       NULL,
                       role
                       TEXT
                       NOT
                       NULL,
                       content
                       TEXT
                       NOT
                       NULL,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
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
    """动态加载 skills 包下所有模块，提取 Skill 定义和执行函数"""
    skill_definitions = []
    skill_executors = {}

    for finder, name, ispkg in pkgutil.iter_modules(skills.__path__):
        module = importlib.import_module(f"skills.{name}")
        if hasattr(module, "get_skill_definition") and hasattr(module, "execute"):
            skill_definitions.append(module.get_skill_definition())
            skill_executors[name] = module.execute
            print(f"Loaded skill: {name}")

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
async def root():
    return {"message": "AI 服务已启动，请使用 POST 请求访问 /chat"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

    # 保存用户消息
    save_message(session_id, "user", request.message)

    # 获取历史（最近10条）
    history = get_history(session_id, limit=10)
    messages = history + [{"role": "user", "content": request.message}]

    # 调用 DeepSeek API，带上 Skill 定义
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

        # 检查是否有 tool_calls
        if message.get("tool_calls"):
            tool_call = message["tool_calls"][0]
            function_name = tool_call["function"]["name"]
            arguments = eval(tool_call["function"]["arguments"])  # 安全起见可用 json.loads
            # 找到对应的 executor
            executor = None
            for name, exec_func in SKILL_EXECUTORS.items():
                # 匹配 skill 名（与定义中的 name 对应）
                if function_name == getattr(importlib.import_module(f"skills.{name}"), "SKILL_NAME", ""):
                    executor = exec_func
                    break
            if executor:
                tool_result = executor(**arguments)
                # 把工具结果返回给 AI 生成最终回答
                messages.append(message)  # 包含 tool_calls 的 assistant 消息
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": tool_result
                })
                # 第二次调用 AI 生成最终回答
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


# ================ 启动服务（仅本地开发） ================
if __name__ == "__main__":
    import uvicorn

    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)