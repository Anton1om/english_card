CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY,
    username VARCHAR(40) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS common_words(
    id SERIAL PRIMARY KEY,
    russian_word VARCHAR(80) NOT NULL,
    english_word VARCHAR(80) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT common_words_uniq UNIQUE (russian_word, english_word)
);

CREATE TABLE IF NOT EXISTS user_words(
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    russian_word VARCHAR(80) NOT NULL,
    english_word VARCHAR(80) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT user_words_uniq UNIQUE (user_id, russian_word, english_word)
);

CREATE TABLE IF NOT EXISTS learning_stats(
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    word_id INTEGER NOT NULL,
    word_type VARCHAR(10) NOT NULL,
    correct_answers INTEGER NOT NULL DEFAULT 0,
    total_attempts INTEGER NOT NULL DEFAULT 0,
    last_reviewed TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT learning_stats_uniq UNIQUE (user_id, word_id, word_type),
    CONSTRAINT word_type_check CHECK (word_type IN ('common', 'user'))
);