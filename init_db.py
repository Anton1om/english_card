from db import get_db_connection


def init_database():
    """
    Создание и первичное заполнение таблиц.
    Описано в файлах create_tables.sql и insert_data.sql
    Создаются таблицы:
    1. users (id, username, created_at)
    2. common_words (id, russian_word, english_word, created_at)
    3. user_words (id, user_id, russian_word, english_word, created_at)
    4. learning_stats (id, user_id, word_id, word_type, correct_answers, total_attempts, last_reviewed)

    Заполняются таблицы:
    1. common_words
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            with open('sql/create_tables.sql', 'r', encoding='utf-8') as f:
                create_table = f.read()

            cur.execute(create_table)
            conn.commit()

            with open('sql/insert_data.sql', 'r', encoding='utf-8') as f:
                insert_data = f.read()

            cur.execute(insert_data)
            conn.commit()