# ============================================================
# ИНТЕРФЕЙС ПРИЛОЖЕНИЯ
# ============================================================
import pandas as pd
import streamlit as st
import random
import config
import logic
import db


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
                elif len(username) > config.MAX_USERNAME_LENGTH:
                    st.error(f"❌ Логин должен быть не более {config.MAX_USERNAME_LENGTH} символов")
                else:
                    st.session_state.username = username.strip()
                    st.session_state.user_id = db.login_user(st.session_state.username)
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
    st.session_state.setdefault('current_options', logic.generate_options(st.session_state.current_word_id, words))
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
                db.update_stats(st.session_state.user_id, word['id'], word['word_type'], option['is_correct'])

                st.rerun()

    # --- Кнопка "Следующее слово"

    if st.button("➡️ Следующее слово", use_container_width=True):
        st.session_state.current_word_id = random.randrange(0, len(words))
        st.session_state.current_options = logic.generate_options(st.session_state.current_word_id, words)
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
            elif len(russian_word) > config.MAX_WORD_LENGTH or len(english_word) > config.MAX_WORD_LENGTH:
                st.session_state.add_input_message = (
                    "error",
                    f"❌ Значения более {config.MAX_WORD_LENGTH} символов не поддерживаются"
                )
            else:
                # Добавляем поле в БД, рассчитываем количество полей для изучения
                result = db.add_personal_word(st.session_state.user_id, russian_word, english_word)
                _, user_words_count = logic.calc_words_count(words)
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
                tmp = logic.translate_word(russian_word)
                if tmp:
                    st.session_state.auto_russian_input = russian_word
                    st.session_state.auto_english_input = tmp
                    st.session_state.reset_input = True
                else:
                    st.session_state.add_input_message = ("error", "❌ Не удалось перевести слово")
            elif english_word and not russian_word:
                tmp = logic.translate_word(english_word, "en-ru")
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

            db.delete_personal_word(st.session_state.user_id, selected_id)  # функция удаления из БД
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
    stat = db.get_statistics(user_id)
    common_words_count, user_words_count = logic.calc_words_count(words)

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
            st.image("assets/english_card.png")
        except FileNotFoundError:
            st.error("❌ Файл english_card.png не найден")

