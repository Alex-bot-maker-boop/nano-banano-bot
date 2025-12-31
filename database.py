import sqlite3
import logging

logger = logging.getLogger(__name__)

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            free_uses INTEGER DEFAULT 3,
            paid_uses INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

def add_user(user_id, username):
    """Добавление нового пользователя"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username) 
            VALUES (?, ?)
        ''', (user_id, username))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Ошибка добавления пользователя: {e}")

def get_user(user_id):
    """Получение данных пользователя"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"❌ Ошибка получения пользователя: {e}")
        return None

def update_balance(user_id, free_uses=0, paid_uses=0):
    """Обновление баланса пользователя"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET free_uses = free_uses + ?, paid_uses = paid_uses + ?
            WHERE user_id = ?
        ''', (free_uses, paid_uses, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Ошибка обновления баланса: {e}")
