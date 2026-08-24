# ============================================================
# ОПРЕДЕЛЕНИЕ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ И КОНСТАНТ
# ============================================================

import os
from dotenv import load_dotenv


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
