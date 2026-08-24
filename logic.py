# ============================================================
# ЛОГИКА И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
import random
import requests
import config


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

    if not config.YANDEX_TRANSLATE_TOKEN:
        return None

    try:
        resp = requests.get(config.YANDEX_TRANSLATE_URL,
                            params={"key": config.YANDEX_TRANSLATE_TOKEN, "lang": lang, "text": word})
        result = resp.json()
        trans_word = result["def"][0]["tr"][0]["text"]
    except:
        return None

    return trans_word
