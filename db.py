# ============================================================
# РАБОТА С БАЗОЙ ДАННЫХ
# ============================================================

import psycopg2
import psycopg2.extras
import config

def get_db_connection():
    """
    Функция подключения к БД
    Параметры подключения прописаны в .env файле и загружаются при запуске приложения
    """
    conn = psycopg2.connect(host=config.HOST, port=config.PORT, database=config.DATABASE,
                            user=config.USER, password=config.PASSWORD)
    return conn


def login_user(username):
    """
    Если пользователя нет - функция создает нового и возвращает его id
    Если пользователь существует - функция просто возвращает его id
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (username) VALUES (%s)
                ON CONFLICT (username) DO NOTHING
                RETURNING id;
                """, (username,))
            row = cur.fetchone()
            if row is not None:
                return row[0]
            cur.execute("SELECT id FROM users WHERE username = %s;", (username,))
            return cur.fetchone()[0]


def get_user_words(user_id):
    """
    Функция возвращает все слова пользователя (общие и персональные)
    Возвращает список словарей: [{'id': 1, 'russian_word': 'красный', 'english_word': 'red', 'word_type': 'common'}, ...]
    word_type принимает значения либо 'common', либо 'user'
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, russian_word, english_word, 'common' AS word_type 
                FROM common_words
                UNION ALL
                SELECT id, russian_word, english_word, 'user' AS word_type 
                FROM user_words 
                WHERE user_id = %s
                """, (user_id,))
            rows = cur.fetchall()
            return rows


def add_personal_word(user_id, russian_word, english_word):
    """
    Функция добавляет персональное слово для пользователя, в этом случае возвращает True
    Если такое слово уже есть, возвращает False
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_words (user_id, russian_word, english_word) 
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, russian_word, english_word) DO NOTHING
                RETURNING id;
                """, (user_id, russian_word, english_word))
            row = cur.fetchone()
            if row is None:
                return False
            else:
                return True


def delete_personal_word(user_id, word_id):
    """
    Функция удаляет персональное слово пользователя, а также статистику по этому слово.
    В этом случае возвращает True
    Если такого слова нет, удаления не происходит и функция возвращает False
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM learning_stats
                WHERE user_id = %s AND word_id = %s AND word_type = 'user'
            """, (user_id, word_id))
            cur.execute("""
                DELETE FROM user_words
                WHERE id = %s AND user_id = %s
                RETURNING id
            """, (word_id, user_id))
            deleted = cur.fetchone()
            return deleted is not None


def update_stats(user_id, word_id, word_type, is_correct):
    """
    Обновляет статистику пользователя для конкретного слова.
    Увеличивает total_attempts на 1, correct_answers на 1 (если is_correct=True),
    Обновляет last_reviewed на текущее время.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO learning_stats (user_id, word_id, word_type, correct_answers, total_attempts)
                VALUES (%s, %s, %s, %s, 1)
                ON CONFLICT (user_id, word_id, word_type) DO UPDATE
                SET total_attempts = learning_stats.total_attempts + 1,
                    correct_answers = learning_stats.correct_answers + %s,
                    last_reviewed = NOW()
            """, (user_id, word_id, word_type, 1 if is_correct else 0, 1 if is_correct else 0))


def get_statistics(user_id):
    """
    Возвращает словарь со статистикой пользователя + добавляет значения слов из связанных таблиц
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT ls.word_id, ls.word_type, ls.correct_answers, ls.total_attempts, ls.last_reviewed,
                COALESCE(cw.russian_word, uw.russian_word) AS russian_word,
                COALESCE(cw.english_word, uw.english_word) AS english_word
                FROM learning_stats ls
                LEFT JOIN common_words cw
                ON ls.word_type = 'common' AND ls.word_id = cw.id
                LEFT JOIN user_words uw 
                ON ls.word_type = 'user' AND ls.word_id = uw.id
                WHERE ls.user_id = %s
                ORDER BY ls.word_type, ls.word_id;
                """, (user_id,))
            rows = cur.fetchall()
            return rows
