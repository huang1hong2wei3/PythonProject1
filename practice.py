import sqlite3
def get_all_sessions(db_path="chat_history.db"):
    try:
        conn=sqlite3.connect(db_path)
        cursor=conn.cursor()
        cursor.execute("SELECT DISTINCT session_id FROM conversations")
        rows=cursor.fetchall()
        conn.close()
        return [r[0] for row in rows]
    except sqlite3.Error:
        return []
