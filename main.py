"""
EnglishCard - Приложение для изучения английского языка
"""
import streamlit as st
from init_db import init_database
import db
import ui


# ============================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================


st.set_page_config(
    page_title="EnglishCard - Изучение английского",
    page_icon="📚",
    layout="wide"
)


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
    ui.render_sidebar()

    # Основной контент в зависимости от авторизации
    if st.session_state.user_id:
        words = db.get_user_words(st.session_state.user_id)
        # Создание вкладок
        tab1, tab2, tab3, tab4 = st.tabs(["📖 Изучение", "➕ Добавление", "🗑️ Удаление", "📊 Статистика"])
        with tab1:
            ui.render_study_tab(words)
            ui.render_schema()
        with tab2:
            ui.render_add_word_tab(words)
        with tab3:
            ui.render_delete_word_tab(words)
        with tab4:
            ui.render_statistics_tab(st.session_state.user_id, words)
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