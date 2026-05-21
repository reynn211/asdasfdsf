# ЧастоСлов — Анализатор текста для подсчёта частоты слов

Веб-сервис для статистического анализа текстов: подсчёт частот слов, визуализация, стемминг, n-граммы, экспорт и сравнение документов.

![CI](https://github.com/<owner>/<repo>/actions/workflows/ci.yml/badge.svg)

---

## Содержание

1. [Возможности](#возможности)
2. [Архитектура](#архитектура)
3. [Стек технологий](#стек-технологий)
4. [Алгоритмы и сложность](#алгоритмы-и-сложность)
5. [Быстрый запуск](#быстрый-запуск)
6. [Docker Compose](#docker-compose)
7. [API](#api)
8. [CI / CD](#ci--cd)
9. [Тестирование](#тестирование)
10. [Примеры использования](#примеры-использования)
11. [Структура проекта](#структура-проекта)

---

## Возможности

- Загрузка `.txt`, `.docx`, `.pdf` (до 50 МБ)
- Автоматическое определение кодировки (UTF-8, UTF-16, CP1251 и др.)
- Подсчёт частоты слов с сортировкой и поиском
- Стемминг Porter для русского и английского языков
- N-граммы (биграммы, триграммы)
- Удаление стоп-слов (RU/EN, авто-определение языка)
- Метрики читаемости (Flesch, средняя длина слова/предложения)
- Гистограмма частот с настраиваемым Top-N
- Экспорт в CSV / XLSX / JSON
- Сравнение двух документов (diff по частотам)
- История анализов (SQLite, привязка по cookie-сессии)
- Тёмная / светлая тема
- Адаптивный интерфейс (desktop / tablet / mobile)

---

## Архитектура

```
┌────────────────────┐         ┌──────────────────────────────────┐
│                    │  /api/* │                                  │
│   React SPA       │────────▶│  FastAPI (Python)                 │
│   (Vite + nginx)  │◀────────│    ├── extract_text()            │
│                    │  JSON   │    ├── subprocess → C++ analyzer │
│                    │         │    ├── fallback (Python)         │
└────────────────────┘         │    └── SQLite (история)         │
                               │                                  │
                               │  C++ analyzer binary:            │
                               │    tokenizer → stop_words →      │
                               │    stemmer → ngrams →            │
                               │    readability → JSON stdout     │
                               └──────────────────────────────────┘
```

**Потоки данных:**
1. Пользователь загружает файл через браузер (React Dropzone)
2. Frontend отправляет `multipart/form-data` на `/api/analyze`
3. Backend извлекает текст (python-docx / pypdf / charset-normalizer)
4. Текст передаётся в C++ анализатор через `subprocess` (stdin → stdout)
5. Если C++ бинарник недоступен — используется Python fallback
6. Результат сохраняется в SQLite и возвращается как JSON
7. Frontend рендерит таблицу, гистограмму, метрики

---

## Стек технологий

| Уровень | Технология | Назначение |
|---------|-----------|------------|
| Frontend | React 19, Vite 8, CSS (без фреймворков) | SPA, визуализация |
| Backend | Python 3.12, FastAPI, Uvicorn | REST API, оркестрация |
| Анализатор | C++17, CMake | Высокопроизводительная обработка текста |
| БД | SQLite | История анализов |
| Инфра | Docker, docker-compose, nginx | Контейнеризация, прокси |
| CI | GitHub Actions | Линтинг, тесты, сборка |

---

## Алгоритмы и сложность

### 1. Токенизация (UTF-8)

**Алгоритм:** Посимвольный проход по UTF-8 тексту. Символ классифицируется как «часть слова» (буква Unicode / цифра / апостроф) или разделитель. Слова приводятся к lowercase.

**Сложность:** `O(n)` по длине текста (один проход).

### 2. Подсчёт частот

**Структура:** `std::unordered_map<std::string, int>` (хеш-таблица).

**Сложность:**
- Вставка / поиск: `O(1)` амортизированно, `O(n)` в худшем случае
- Общий подсчёт по `m` токенам: `O(m)` в среднем

### 3. Сортировка по частоте

**Алгоритм:** `std::sort` (introsort) по убыванию count, при равенстве — лексикографически.

**Сложность:** `O(k log k)`, где `k` — количество уникальных слов.

### 4. Стемминг (Porter)

**Алгоритм:**
- Английский: Porter Stemmer 1980 (5 шагов: удаление суффиксов `-ed`, `-ing`, `-tion`, и т.д.)
- Русский: Snowball Russian Stemmer (удаление окончаний, суффиксов прилагательных, глаголов, причастий)

**Диспатчинг:** если все кодпоинты токена — кириллица → RU стеммер; все ASCII → EN стеммер; смешанные/числа → без изменений.

**Сложность:** `O(L)` на токен, где `L` — длина слова (фиксированное число шагов, каждый — линейный проход по суффиксу).

### 5. N-граммы

**Алгоритм:** Скользящее окно размера `n` по последовательности обработанных (отфильтрованных, стеммированных) токенов. Фразы конкатенируются через пробел, подсчитываются аналогично unigrams.

**Сложность:** `O(m)` для построения, `O(k_n log k_n)` для сортировки (`k_n` — уникальные n-граммы).

### 6. Определение языка

**Алгоритм:** Подсчёт кириллических vs. латинских кодпоинтов по всему тексту. Если кириллица > 50% букв → `"ru"`, иначе `"en"`. Если букв нет → `"unknown"`.

**Сложность:** `O(n)` — один проход.

### 7. Метрики читаемости

- **Средняя длина слова** = Σ(длина в кодпоинтах) / кол-во слов — `O(m)`
- **Средняя длина предложения** = кол-во слов / кол-во предложений (предложения разделяются по `.!?`) — `O(n)`
- **Flesch Reading Ease** = 206.835 − 1.015 × ASL − 84.6 × ASW (англ.) / адаптированная формула для рус.

### 8. Стоп-слова

**Структура:** `std::unordered_set<std::string>` — загружается из файла.

**Сложность:** Проверка одного токена — `O(1)` амортизированно. Фильтрация `m` токенов — `O(m)`.

### Общая сложность обработки файла

`O(n + m + k log k)`, где:
- `n` — размер файла в байтах (токенизация + определение языка)
- `m` — количество токенов (подсчёт, фильтрация, стемминг, n-граммы)
- `k` — количество уникальных слов (сортировка)

На практике для «Война и мир» (~3.2 МБ, ~580 000 слов) — обработка занимает < 1 секунды на C++.

---

## Быстрый запуск

### Требования

- Python 3.11+
- Node.js 18+
- CMake 3.12+ и компилятор C++17 (g++ 9+, clang 10+, MSVC 2019+)

### Backend

```bash
cd backend
pip install -r requirements.txt

# Сборка C++ анализатора
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build

# Запуск сервера (dev)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend откроется на `http://localhost:5173` и проксирует `/api/*` на `http://localhost:8000`.

---

## Docker Compose

Из корня репозитория:

```bash
docker compose up --build
```

Сервисы:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000 (Swagger UI: `/docs`)

Frontend-контейнер (nginx) проксирует запросы `/api/*` на backend по внутренней docker-сети. SQLite-история (`app.db`) сохраняется в именованном volume `backend-data`.

```bash
# Остановить
docker compose down

# Полностью очистить (включая историю)
docker compose down -v
```

---

## API

### `POST /api/analyze`

Загрузка файла и анализ.

**Form params:**

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `file` | File | (обязательный) | .txt / .docx / .pdf |
| `exclude_stopwords` | bool | `true` | Удалять стоп-слова |
| `language` | string | `"auto"` | `auto` / `ru` / `en` |
| `min_length` | int | `0` | Мин. длина слова |
| `top_n` | int | `0` | Ограничить топ-N (0 = все) |
| `ignore_numbers` | bool | `true` | Пропускать числа |
| `ngram` | int | `1` | 1 / 2 / 3 |
| `normalize` | string | `"stem"` | `stem` / `none` |

**Ответ (200):**
```json
{
  "id": 42,
  "total_words": 5823,
  "unique_words": 1247,
  "language": "ru",
  "frequencies": {"слово": 83, "текст": 41, ...},
  "ngrams": {"2": {"слово текст": 12, ...}},
  "readability": {
    "avg_word_length": 5.42,
    "avg_sentence_length": 14.8,
    "flesch": 62.3
  }
}
```

**Ошибки:** `413` (файл > 50 МБ), `422` (битый docx/pdf, неизвестный формат).

### `GET /api/history`

Список последних анализов текущей сессии (без тяжёлых `frequencies`).

### `GET /api/history/{id}`

Полный результат конкретного анализа.

### `DELETE /api/history/{id}`

Удалить запись из истории.

### `GET /api/export/{id}?format=csv|xlsx|json`

Экспорт результата в выбранном формате.

---

## CI / CD

Конфигурация: `.github/workflows/ci.yml`

### Что запускается:

| Job | Шаги |
|-----|------|
| `backend` | `ruff check` → `ruff format --check` → CMake build → `pytest` |
| `analyzer` | CMake configure → build → `ctest` (C++ unit-тесты) |
| `frontend` | `npm ci` → `eslint` → `vite build` |

### Локальное тестирование CI

Используйте [`act`](https://github.com/nektos/act) — инструмент для запуска GitHub Actions локально через Docker:

```bash
# Установка (Windows, через scoop/choco/go)
scoop install act
# или
go install github.com/nektos/act@latest

# Запуск всех jobs
act

# Запуск конкретного job
act -j backend
act -j analyzer
act -j frontend

# С verbose-логами
act -v -j backend
```

**Требования:** Docker Desktop должен быть запущен. `act` скачает образы `ubuntu-latest` (~1.5 ГБ при первом запуске).

**Совет:** Если `act` тормозит на полных образах, используйте micro-образы:
```bash
act -P ubuntu-latest=catthehacker/ubuntu:act-latest
```

---

## Тестирование

### Python (pytest)

```bash
cd backend
pytest -v
```

45 тестов покрывают: `/api/analyze`, `/api/history`, `DELETE`, экспорт, fallback-обработку, n-граммы, стоп-слова по языку, определение кодировки, обработку ошибок.

### C++ (ctest)

```bash
cd backend/build
ctest --output-on-failure
```

Тесты:
- `tokenizer_tests` — UTF-8 токенизация, обработка знаков препинания, Unicode
- `stemmer_tests` — Porter EN (классические примеры), RU (склонения, прилагательные, глаголы), диспатчер, n-граммы

### Frontend (ESLint)

```bash
cd frontend
npm run lint
```

---

## Примеры использования

### Через cURL

```bash
# Простой анализ текстового файла
curl -F "file=@document.txt" http://localhost:8000/api/analyze

# С фильтрами
curl -F "file=@book.pdf" \
     -F "exclude_stopwords=true" \
     -F "language=ru" \
     -F "min_length=3" \
     -F "top_n=100" \
     -F "ngram=2" \
     -F "normalize=stem" \
     http://localhost:8000/api/analyze

# Экспорт в CSV
curl -o result.csv "http://localhost:8000/api/export/1?format=csv"

# История анализов
curl http://localhost:8000/api/history
```

### Через Python

```python
import requests

with open("war_and_peace.txt", "rb") as f:
    resp = requests.post(
        "http://localhost:8000/api/analyze",
        files={"file": ("war_and_peace.txt", f)},
        data={
            "exclude_stopwords": "true",
            "language": "ru",
            "normalize": "stem",
            "ngram": "2",
        },
    )

data = resp.json()
print(f"Всего слов: {data['total_words']}")
print(f"Уникальных: {data['unique_words']}")
print(f"Язык: {data['language']}")
print(f"Топ-5: {list(data['frequencies'].items())[:5]}")
```

---

## Структура проекта

```
.
├── backend/
│   ├── main.py              # FastAPI-приложение
│   ├── database.py          # SQLite: init, CRUD
│   ├── stop_words.py        # Python-списки стоп-слов (fallback)
│   ├── CMakeLists.txt       # Сборка C++ анализатора
│   ├── requirements.txt     # Python-зависимости
│   ├── data/
│   │   ├── stop_words.txt       # Общий список стоп-слов
│   │   ├── stop_words_ru.txt    # Русские стоп-слова
│   │   └── stop_words_en.txt    # Английские стоп-слова
│   ├── include/analyzer/    # C++ заголовочные файлы
│   │   ├── tokenizer.hpp
│   │   ├── stemmer.hpp
│   │   ├── stop_words.hpp
│   │   ├── ngrams.hpp
│   │   ├── language.hpp
│   │   ├── readability.hpp
│   │   └── json_writer.hpp
│   ├── src/                 # C++ реализация
│   │   ├── analyzer_main.cpp
│   │   ├── tokenizer.cpp
│   │   ├── stemmer.cpp
│   │   ├── stop_words.cpp
│   │   ├── ngrams.cpp
│   │   ├── language.cpp
│   │   └── readability.cpp
│   └── tests/
│       ├── test_api.py          # Интеграционные тесты API
│       ├── test_fallback.py     # Тесты Python fallback
│       ├── tokenizer_tests.cpp  # C++ тесты токенизатора
│       └── stemmer_tests.cpp    # C++ тесты стеммера
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Главный компонент
│   │   ├── App.css          # Стили (адаптивные)
│   │   ├── Comparison.jsx   # Сравнение документов
│   │   ├── index.css        # CSS-переменные, темы
│   │   └── components/
│   │       ├── Dropzone.jsx     # Drag & drop загрузка
│   │       ├── FreqTable.jsx    # Таблица частот
│   │       ├── Histogram.jsx    # Гистограмма
│   │       ├── FiltersPanel.jsx # Панель фильтров
│   │       └── Icon.jsx         # SVG-иконки
│   ├── nginx.conf           # Прокси /api/* → backend
│   └── package.json
├── .github/workflows/
│   └── ci.yml               # GitHub Actions CI
├── docker-compose.yml
└── README.md
```

---

## Деплой на Render (бесплатно)

1. Форкните/запушьте репозиторий на GitHub
2. Зайдите на [render.com](https://render.com) → **New** → **Blueprint**
3. Подключите репозиторий — Render найдёт `render.yaml` автоматически
4. Нажмите **Apply** — сборка займёт ~3-5 минут (C++ + Node + Python)
5. Получите URL вида `https://chastoslov.onrender.com`

**Или вручную:**
1. **New** → **Web Service** → подключите репозиторий
2. Environment: **Docker**
3. Dockerfile Path: `./Dockerfile`
4. Plan: **Free**
5. Deploy

> ⚠️ На бесплатном тарифе сервис засыпает после 15 минут неактивности.
> Первый запрос после сна занимает ~30-60 секунд (cold start).
> История анализов (SQLite) сбрасывается при каждом деплое.

---

## Лицензия

Учебный проект. Свободное использование.
