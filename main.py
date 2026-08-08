"""
EnglishCard - Приложение для изучения английского языка
"""
import os
from dotenv import load_dotenv
import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import random
import requests


# ============================================================
# ОПРЕДЕЛЕНИЕ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ И КОНСТАНТ
# ============================================================


load_dotenv()
DATABASE = os.getenv('DB_NAME')
HOST = os.getenv('DB_HOST')
PORT = os.getenv('DB_PORT')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')
MAX_USERNAME_LENGTH = 40
MAX_WORD_LENGTH = 80
YANDEX_TRANSLATE_TOKEN = os.getenv('YANDEX_TRANSLATE_TOKEN')
YANDEX_TRANSLATE_URL = 'https://dictionary.yandex.net/api/v1/dicservice.json/lookup'


# ============================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================


st.set_page_config(
    page_title="EnglishCard - Изучение английского",
    page_icon="📚",
    layout="wide"
)


# ============================================================
# РАБОТА С БАЗОЙ ДАННЫХ
# ============================================================


def get_db_connection():
    """
    Функция подключения к БД
    Параметры подключения прописаны в .env файле и загружаются при запуске приложения
    """
    conn = psycopg2.connect(host=HOST, port=PORT, database=DATABASE, user=USER, password=PASSWORD)
    return conn


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
            with open('create_tables.sql', 'r', encoding='utf-8') as f:
                create_table = f.read()

            cur.execute(create_table)
            conn.commit()

            with open('insert_data.sql', 'r', encoding='utf-8') as f:
                insert_data = f.read()

            cur.execute(insert_data)
            conn.commit()


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


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================


def generate_options(correct_word_id, all_words):
    """
    На вход функции принимается - словарь всех слов пользователя и id правильного ответа из этого словаря
    Функция генерирует 4 варианта для викторины
    Генерация вариантов происходит с учетом того, что у слова может быть несколько правильных переводов
    На выходе возвращается список из 4 словарей, каждый словарь содержит english_word и признак is_correct
    """
    def extract(item, is_correct):
        keys = ('english_word', )
        d = {k: item[k] for k in keys}
        d['is_correct'] = is_correct
        return d

    result = []
    tmp_words = all_words.copy()
    tmp_words.pop(correct_word_id)
    additional_words = random.sample(range(len(tmp_words)), 3)
    result.append(extract(all_words[correct_word_id], True))

    for i in additional_words:
        if tmp_words[i]['russian_word'] == all_words[correct_word_id]['russian_word']:
            result.append(extract(tmp_words[i], True))
        else:
            result.append(extract(tmp_words[i], False))
    random.shuffle(result)
    return result


def calc_words_count(words):
    """
    Техническая функция подсчета количества общих слов и слов пользователя в общем списке
    """
    common_words_count = len([word for word in words if word['word_type'] == 'common'])
    user_words_count = len([word for word in words if word['word_type'] == 'user'])
    return common_words_count, user_words_count


def translate_word(word, lang = "ru-en"):
    """
    Функция запроса перевода в yandex translate api.
    Поддерживает перевод с русского на английский, с английского на русский.
    Возвращает 1 полученное слово
    """
    if lang not in ("ru-en", "en-ru"):
        return None

    if not YANDEX_TRANSLATE_TOKEN:
        return None

    try:
        resp = requests.get(YANDEX_TRANSLATE_URL,
                        params={"key": YANDEX_TRANSLATE_TOKEN, "lang": lang, "text": word})
        result = resp.json()
        trans_word = result["def"][0]["tr"][0]["text"]
    except:
        return None

    return trans_word


# ============================================================
# ИНТЕРФЕЙС ПРИЛОЖЕНИЯ
# ============================================================


def render_sidebar():
    """
    Боковая панель с авторизацией:
    - Если это гость: поле для логина + кнопка "Войти".
    - После входа: приветствие + кнопка "Выйти".
    После нажатия кнопки выйти session_state очищается полностью
    """
    with st.sidebar:
        st.header("👤 Профиль")

        # --- Состояние: пользователь уже вошёл ---
        if st.session_state.user_id:
            st.success(f"✅ Вы вошли как **{st.session_state.username}**")
            if st.button("🚪 Выйти", use_container_width=True):
                st.session_state.clear()
                st.rerun()

        # --- Состояние: гость ---
        else:
            username = st.text_input("Ваш логин")
            if st.button("🔑 Войти", use_container_width=True):
                if not username or not username.strip():
                    st.error("❌ Логин не может быть пустым!")
                elif len(username) > MAX_USERNAME_LENGTH:
                    st.error(f"❌ Логин должен быть не более {MAX_USERNAME_LENGTH} символов")
                else:
                    st.session_state.username = username.strip()
                    st.session_state.user_id = login_user(st.session_state.username)
                    st.rerun()


def render_study_tab(words):
    """
    Вкладка изучения слов
    - Отображение текущего слова на русском
    - 4 кнопки с вариантами перевода
    - Обработка правильных/неправильных ответов
    - Кнопка следующего слова
    """

    # Проверка
    if not words:
        st.warning("Словарь пуст. Добавьте слова во вкладке «➕ Добавление».")
        return

    # --- Инициализация состояния ---
    st.session_state.setdefault('current_word_id', random.randrange(0, len(words)))
    st.session_state.setdefault('current_options', generate_options(st.session_state.current_word_id, words))
    st.session_state.setdefault('answered', False)
    st.session_state.setdefault('result', None)
    st.session_state.setdefault('selected_option', None)

    # Текущее слово для отображения
    word = words[st.session_state.current_word_id]

    # --- Отображение ---
    header1, header2 = st.columns(2)
    with header1:
        st.write(f"**Слово: {word['russian_word']}**")
        st.write("**Как будет по-английски? Выберите перевод**")

    with header2:
        if st.session_state.result == "correct":
            st.success(f"✅ Правильно! Молодец! (вы выбрали «{st.session_state.selected_option}»)")
        elif st.session_state.result == "incorrect":
            st.error(f"😭 Неверный ответ (вы выбрали «{st.session_state.selected_option}»)")

    # --- Кнопки вариантов (4 в ряд) ---
    options = st.session_state.current_options
    cols = st.columns(4)
    for i, option in enumerate(options):
        with cols[i]:
            if st.button(
                    f"**{option['english_word']}**",
                    key=f"opt_{i}",
                    use_container_width=True,
                    disabled=st.session_state.answered
            ):
                # Обработка выбора
                st.session_state.selected_option = option['english_word']
                st.session_state.result = "correct" if option['is_correct'] else "incorrect"
                st.session_state.answered = True
                # Обновление статистики
                update_stats(st.session_state.user_id, word['id'], word['word_type'], option['is_correct'])

                st.rerun()

    # --- Кнопка "Следующее слово"

    if st.button("➡️ Следующее слово", use_container_width=True):
        st.session_state.current_word_id = random.randrange(0, len(words))
        st.session_state.current_options = generate_options(st.session_state.current_word_id, words)
        st.session_state.answered = False
        st.session_state.result = None
        st.session_state.selected_option = None
        st.rerun()


def render_add_word_tab(words):
    """
    Вкладка добавления нового слова.
    - Два поля ввода (с ключами для session_state)
    - Кнопка «Добавить» – с учетом валидации значений, после добавления поля очищаются
    - Кнопка «Автоперевод» – если заполнено одно из полей, то по нему запрашивается api yandex translate
    и полученное оттуда значение автоматически подставляется в другое поле
    - Кнопка «Очистить» – сброс значений обоих полей
    - Сообщения об ошибках / успехе сохраняются в session_state и показываются после rerun
    """
    # Значения полей ввода
    if "russian_input" not in st.session_state:
        st.session_state.russian_input = ""
    if "english_input" not in st.session_state:
        st.session_state.english_input = ""

    # Значения для автоматического перевода
    if "auto_english_input" not in st.session_state:
        st.session_state.auto_english_input = ""
    if "auto_russian_input" not in st.session_state:
        st.session_state.auto_russian_input = ""

    # Отображение сообщений об ошибках\успехах
    if "add_input_message" not in st.session_state:
        st.session_state.add_input_message = None

    # Очистка \ перезапись полей ввода после всех действий
    if "reset_input" in st.session_state and st.session_state.reset_input:
        st.session_state.russian_input = st.session_state.auto_russian_input
        st.session_state.english_input = st.session_state.auto_english_input
        st.session_state.reset_input = False

    st.text_input("Слово на русском", key="russian_input")
    st.text_input("Перевод на английский", key="english_input")

    # Очищаем от пробелов, приводим к нижнему регистру
    russian_word = st.session_state.russian_input.strip().lower()
    english_word = st.session_state.english_input.strip().lower()


    col1, col2, col3 = st.columns(3)
    # Логика кнопки Добавить - валидация на наличие значений и длину полей
    with col1:
        if st.button("📌 Добавить", use_container_width=True):
            if not russian_word:
                st.session_state.add_input_message = ("error", "❌ Слово не может быть пустым")
            elif not english_word:
                st.session_state.add_input_message = ("error", "❌ Перевод не может быть пустым")
            elif len(russian_word) > MAX_WORD_LENGTH or len(english_word) > MAX_WORD_LENGTH:
                st.session_state.add_input_message = (
                    "error",
                    f"❌ Значения более {MAX_WORD_LENGTH} символов не поддерживаются"
                )
            else:
                # Добавляем поле в БД, рассчитываем количество полей для изучения
                result = add_personal_word(st.session_state.user_id, russian_word, english_word)
                _, user_words_count = calc_words_count(words)
                if result:
                    st.session_state.add_input_message = (
                        "success",
                        f"✍️ Слово **{russian_word} – {english_word}** добавлено. Итого слов: {user_words_count + 1}"
                    )
                else:
                    st.session_state.add_input_message= (
                        "info",
                        f"👍 Слово **{russian_word} – {english_word}** уже есть в вашем словаре"
                    )
                st.session_state.reset_input = True
                st.session_state.auto_english_input = ""
                st.session_state.auto_russian_input = ""
            st.rerun()

    # Логика кнопки автоматического перевода - запрашиваем API, если заполнено 1 из полей
    with col2:
        if st.button("🤖 Автоперевод", use_container_width=True):
            if russian_word and not english_word:
                tmp = translate_word(russian_word)
                if tmp:
                    st.session_state.auto_russian_input = russian_word
                    st.session_state.auto_english_input = tmp
                    st.session_state.reset_input = True
                else:
                    st.session_state.add_input_message = ("error", "❌ Не удалось перевести слово")
            elif english_word and not russian_word:
                tmp = translate_word(english_word, "en-ru")
                if tmp:
                    st.session_state.auto_russian_input = tmp
                    st.session_state.auto_english_input = english_word
                    st.session_state.reset_input = True
                else:
                    st.session_state.add_input_message = ("error", "❌ Не удалось перевести слово")
            else:
                st.session_state.add_input_message= ("info", "Для автоперевода заполните одно из полей")
            st.rerun()

    # Логика кнопки очистки
    with col3:
        if st.button("🧹 Очистить", use_container_width=True):
            st.session_state.reset_input = True
            st.session_state.add_input_message = None
            st.session_state.auto_english_input = ""
            st.session_state.auto_russian_input = ""
            st.rerun()

    # Логика вывода сообщений
    if st.session_state.add_input_message:
        msg_type, msg_text = st.session_state.add_input_message
        if msg_type == "error":
            st.error(msg_text)
        elif msg_type == "success":
            st.success(msg_text)
        elif msg_type == "info":
            st.info(msg_text)
        else:
            st.write(msg_text)
        st.session_state.add_input_message = None


def render_delete_word_tab(words):
    """
    Вкладка удаления слова
    - Выпадающий список с персональными словами пользователя
    - Чекбокс подтверждения удаления
    - Кнопку удаления (становится активной, если нажат чекбокс)
    """
    # Определяем переменную значения чекбокса
    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    # После успешного удаления по флагу reset_delete_checkbox - очищаем значение чекбокса
    if "reset_delete_checkbox" in st.session_state and st.session_state.reset_delete_checkbox:
        st.session_state.confirm_delete = False
        st.session_state.reset_delete_checkbox = False

    # Собираем список слов, доступных для удаления
    words_for_delete = {}
    for word in words:
        if word['word_type'] == 'user':
            words_for_delete[word['id']] = f'{word["russian_word"]} - {word["english_word"]}'

    # Отображаем значения для удаления в выпадающем списке
    if words_for_delete:
        selected_id = st.selectbox(
            "Выберите из списка",
            options=list(words_for_delete.keys()),
            format_func=lambda id: words_for_delete[id]
        )

        confirm = st.checkbox(
            "Я подтверждаю действие. После нажатия кнопки слово будет удалено, а статистика скорректирована",
            key="confirm_delete"   # состояние привязано к session_state
        )

        # Кнопка доступна только, если есть подтверждение confirm
        if st.button("❌ Удалить", disabled=not confirm, use_container_width=True):

            delete_personal_word(st.session_state.user_id, selected_id)  # функция удаления из БД
            st.session_state.delete_success = f"Слово «{words_for_delete[selected_id]}» удалено"
            # После успешного удаления активируем флаг reset_delete_checkbox
            st.session_state.reset_delete_checkbox = True
            st.rerun()
    else:
        st.info("Список персональных слов пуст")

    # Вывод сообщения после успешного удаления
    if "delete_success" in st.session_state and st.session_state.delete_success:
        st.success(st.session_state.delete_success)
        st.session_state.delete_success = ""


def render_statistics_tab(user_id, words):
    """
       Отображает вкладку статистики пользователя.
       - Количество изученных слов
       - Количество попыток
       - Процент правильных ответов
       - Разбивка по типам слов
       - Детальная таблица по каждому слову, отсортированная по убыванию времени
       """
    stat = get_statistics(user_id)
    common_words_count, user_words_count = calc_words_count(words)

    if not stat:
        st.info("Статистика пока отсутствует. Начните изучать слова!")
        return

    df = pd.DataFrame(stat)

    total_learned_words = df['word_id'].nunique()
    total_attempts = df['total_attempts'].sum()
    total_correct = df['correct_answers'].sum()
    accuracy = (total_correct / total_attempts * 100) if total_attempts > 0 else 0.0

    # Отображаем в виде карточек
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📃 Всего слов", common_words_count + user_words_count)
    col2.metric("👤 Слов пользователя", user_words_count)
    col3.metric("📚 Изучено", total_learned_words)
    col4.metric("🔄 Всего попыток", total_attempts)
    col5.metric("🎯 Точность", f"{accuracy:.1f}%")

    st.divider()

    # --- Статистика по типам слов ---
    st.subheader("По типам слов")
    type_stats = df.groupby('word_type').agg(
        words=('word_id', 'nunique'),
        attempts=('total_attempts', 'sum'),
        correct=('correct_answers', 'sum')
    ).reset_index()
    type_stats['accuracy'] = (type_stats['correct'] / type_stats['attempts'] * 100).round(1)
    type_stats['accuracy'] = type_stats['accuracy'].fillna(0).astype(str) + '%'
    type_stats = type_stats.rename(columns={
        'word_type': 'Тип слова',
        'words': 'Количество слов',
        'attempts': 'Всего попыток',
        'correct': 'Правильных ответов',
        'accuracy': 'Точность (%)'
    })
    st.dataframe(type_stats, use_container_width=True, hide_index=True)


    st.divider()

    # --- Детальная таблица по словам ---
    st.subheader("Детальная статистика")
    # Добавляем колонку с процентом для каждого слова
    df['accuracy_per_word'] = (df['correct_answers'] / df['total_attempts'] * 100).round(1)
    df['accuracy_per_word'] = df['accuracy_per_word'].fillna(0).astype(str) + '%'
    df['last_reviewed'] = df['last_reviewed'].dt.strftime('%Y-%m-%d %H:%M')

    display_df = df.rename(columns={
        'russian_word': 'Слово',
        'english_word': 'Перевод',
        'word_type': 'Тип слова',
        'correct_answers': 'Правильно',
        'total_attempts': 'Попытки',
        'last_reviewed': 'Дата проверки',
        'accuracy_per_word': 'Точность (%)'
    })
    desired_order = ['Слово', 'Перевод', 'Тип слова', 'Правильно', 'Попытки', 'Точность (%)', 'Дата проверки']
    display_df = display_df[desired_order]
    display_df = display_df.sort_values('Дата проверки', ascending=False)
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_schema():
    """
    Отображение схемы базы данных
    Схема должна быть сохранена в картинке english_card.png
    """
    with st.expander("💻 Схема базы данных"):
        try:
            st.image("english_card.png")
        except FileNotFoundError:
            st.error("❌ Файл english_card.png не найден")


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================


def main():
    """
    Главная функция приложения
    1. Инициализация БД
    2. Авторизация пользователя
    3. Отображение вкладок с функционалом
    4. Приветственное сообщение для неавторизованных пользователей
    """

    st.title("📚 EnglishCard - Изучай английский с удовольствием!")

    # Инициализация состояния сессии
    if "user_id" not in st.session_state or "username" not in st.session_state:
        st.session_state.user_id = None
        st.session_state.username = ""

    # Инициализация БД
    init_database()

    # Боковая панель с авторизацией
    render_sidebar()

    # Основной контент в зависимости от авторизации
    if st.session_state.user_id:
        words = get_user_words(st.session_state.user_id)
        # Создание вкладок
        tab1, tab2, tab3, tab4 = st.tabs(["📖 Изучение", "➕ Добавление", "🗑️ Удаление", "📊 Статистика"])
        with tab1:
            render_study_tab(words)
            render_schema()
        with tab2:
            render_add_word_tab(words)
        with tab3:
            render_delete_word_tab(words)
        with tab4:
            render_statistics_tab(st.session_state.user_id, words)
        with st.bottom:
            st.caption("""
                Для управления словарем используйте вкладки: ➕ Добавление, 🗑️ Удаление. 
                Сводные результаты обучения доступны на вкладке 📊 Статистика.
                """)
    else:
        st.divider()
        st.markdown("""
        Привет 👋 Давайте попрактикуемся в английском языке. \n
        Тренировки можно проходить в удобном для вас темпе.
        У вас есть возможность использовать тренажёр, как конструктор, и собирать свою собственную базу для обучения.
        Ну что, начнём?\n
        ⬅️ Для продолжения, пожалуйста, введите свой логин
        """)
        st.divider()

if __name__ == "__main__":
    main()