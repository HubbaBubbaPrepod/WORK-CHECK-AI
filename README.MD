# Telegram Analyzer // SYS.CTL

Веб-приложение для анализа сообщений из Telegram-отчётов с использованием LLM (OpenRouter).  
Позволяет автоматически выявлять сообщения, содержащие оппозиционную, экстремистскую или антиправительственную риторику.

## Возможности

- 🕸️ **Парсинг HTML-отчётов** – извлекает сообщения, даты, ID групп.
- 🧠 **Анализ через OpenRouter** – любой LLM-моделью (по умолчанию `openrouter/owl-alpha`).
- ⚡ **Многопоточность** – до 256 параллельных запросов (настраивается).
- 🔁 **Кэширование** – сообщения сохраняются в `parsed_messages.json`, повторный парсинг только при флаге `--force`.
- 🌐 **Веб-интерфейс** – консольный лог в реальном времени через WebSocket, управление анализом.
- 📁 **CSV-отчёты** – `dangerous_openrouter.csv` (все сообщения) и `dangerous_only.csv` (только опасные).

## Требования

- Python 3.9+
- Учётная запись [OpenRouter](https://openrouter.ai/) и API-ключ
- Браузер с поддержкой WebSocket (современный)

## Установка

1. Склонируйте репозиторий:
   ```bash
   git clone https://github.com/HubbaBubbaPrepod/WORK-CHECK-AI.git
   cd WORK_CHECK_AI
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. (Опционально) Создайте файл `.env` для хранения API-ключа (рекомендуется):
   ```env
   OPENROUTER_API_KEY=sk-or-v1-...
   FOLDER=./html_reports
   CACHE_FILE=parsed_messages.json
   OUTPUT_CSV=dangerous_openrouter.csv
   ```

## Настройка

- **API-ключ** – можно указать в `.env` или ввести в веб-интерфейсе.
- **Модель** – выбирается из списка, загруженного через OpenRouter (кнопка `[ FETCH_MODELS ]`).
- **Папка с HTML** – по умолчанию `./html_reports`. Если нужно изменить – укажите в `.env` или передайте аргументом `--folder` при вызове `check.py` (через веб-интерфейс не настраивается, только через серверный код).

> **Важно:** HTML-файлы должны быть экспортированы из Telegram в формате, содержащем `<tbody>` и колонки: дата, ID сообщения, группа (с классом `channel-card`), текст. Структура соответствует стандартному экспорту Telegram Desktop.

## Запуск

### Запуск сервера

```bash
uvicorn backend:app --reload --host 127.0.0.1 --port 8000
```

Сервер раздаёт статику (`index.html`, `script.js`, `style.css`) и предоставляет API:

- `GET /` – веб-интерфейс
- `POST /api/models` – получение списка моделей OpenRouter
- `GET /api/files` – список HTML-файлов в `html_reports`
- `GET /api/cache` – содержимое `parsed_messages.json`
- `WebSocket /ws/run` – запуск анализа с потоковым выводом

### Использование веб-интерфейса

1. Откройте `http://localhost:8000`
2. Введите API-ключ OpenRouter (или нажмите `[ USE_ENV_KEY ]`, если он есть в `.env`)
3. Нажмите `[ FETCH_MODELS ]`, выберите модель из списка
4. Укажите количество потоков (`Max Workers`)
5. При необходимости – включите `FORCE RE-PARSE` (игнорировать кэш)
6. Нажмите `INIT_ANALYSIS`
7. Наблюдайте за логами в реальном времени. По завершении будут созданы CSV-файлы.

### Прямой запуск анализатора (без веб-интерфейса)

```bash
python check.py \
  --folder "./html_reports" \
  --cache "parsed_messages.json" \
  --output "dangerous_openrouter.csv" \
  --api-key "sk-or-v1-..." \
  --model "openrouter/owl-alpha" \
  --max-workers 5 \
  --max-retries 3 \
  [--force]
```

## Структура проекта

```
WORK-CHECK-AI/
├── backend.py          # FastAPI сервер + WebSocket
├── check.py            # Основной скрипт анализа
├── requirements.txt    # Зависимости
├── .env.example        # Пример конфигурации
├── static/             # Фронтенд
│   ├── index.html
│   ├── script.js
│   └── style.css
├── html_reports/       # Папка с HTML-отчётами (создаётся пользователем)
└── README.md
```

## Важные замечания

- **Безопасность**: API-ключ передаётся по WebSocket в открытом виде. Для production используйте HTTPS/WSS и не доверяйте ключи из `.env` клиентской стороне.
- **Кодировка**: На Windows скрипты принудительно используют UTF-8.
- **Ограничения OpenRouter**: Учитывайте стоимость токенов и rate limit. Параллельные запросы могут быстро исчерпать бюджет.
- **Формат HTML**: Если структура ваших отчётов отличается, адаптируйте функцию `parse_html` в `check.py`.

## Лицензия

MIT (или укажите свою). Проект создан в образовательных целях. Авторы не несут ответственности за использование в незаконной деятельности.