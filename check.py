import os
import sys
import json
import csv
import time
import re
import argparse
import threading
import signal
from collections import deque
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

def parse_args():
    parser = argparse.ArgumentParser(description="Анализ Telegram-сообщений через OpenRouter с несколькими ключами")
    parser.add_argument("--folder", default="./html_reports", help="Папка с HTML-файлами")
    parser.add_argument("--cache", default="parsed_messages.json", help="Файл кеша распарсенных сообщений")
    parser.add_argument("--output", default="dangerous_openrouter.csv", help="Выходной CSV-файл")
    parser.add_argument("--api-keys", required=True, help="Список API-ключей через запятую")
    parser.add_argument("--model", required=True, help="Название модели (одна)")
    parser.add_argument("--max-workers", type=int, default=5, help="Количество параллельных потоков")
    parser.add_argument("--max-retries", type=int, default=10, help="Количество повторных попыток при ошибке")
    parser.add_argument("--force", action="store_true", help="Принудительно перепарсить HTML (игнорировать кеш)")
    parser.add_argument("--resume", action="store_true", default=True, help="Возобновить с последнего обработанного сообщения")
    parser.add_argument("--no-resume", dest="resume", action="store_false", help="Не возобновлять, начать заново")
    return parser.parse_args()

args = parse_args()

FOLDER = args.folder
CACHE_FILE = args.cache
OUTPUT_CSV = args.output
MAX_WORKERS = args.max_workers
MAX_RETRIES = args.max_retries
FORCE_PARSE = args.force
MODEL = args.model
RESUME = args.resume

api_keys_list = [k.strip() for k in args.api_keys.split(",") if k.strip()]
if not api_keys_list:
    print("ОШИБКА: Не указано ни одного API ключа", file=sys.stderr)
    sys.exit(1)

print(f"[INIT] Загружено ключей: {len(api_keys_list)}, модель: {MODEL}, resume={RESUME}")

# Пул ключей с состоянием блокировки
key_pool = deque()
for k in api_keys_list:
    key_pool.append({"key": k, "ban_until": None, "failures": 0})

def get_next_api_key():
    """Возвращает рабочий ключ (не забаненный) и переключает его в конец очереди."""
    now = datetime.now()
    for _ in range(len(key_pool)):
        item = key_pool[0]
        if item["ban_until"] is None or item["ban_until"] < now:
            key_pool.rotate(-1)
            return item["key"]
        key_pool.rotate(-1)
    # все ключи забанены – проверяем, стоит ли ждать
    min_ban = min((item["ban_until"] for item in key_pool if item["ban_until"]), default=None)
    if min_ban:
        wait = (min_ban - now).total_seconds()
        if wait > 600:  # если ждать больше 10 минут – выходим, но сохраняем прогресс
            print(f"[FATAL] Все ключи заблокированы надолго (мин. ожидание {wait:.0f} сек). Сохраняем прогресс и выходим.", flush=True)
            sys.exit(2)  # exit code 2 означает "пауза, продолжать позже"
        if wait > 0:
            print(f"[RATE-LIMIT] Все ключи заблокированы, ждём {wait:.1f} сек...", flush=True)
            time.sleep(wait)
        return get_next_api_key()
    return key_pool[0]["key"]

def mark_key_failed(key, ban_duration=60):
    """Помечает ключ как заблокированный на ban_duration секунд."""
    for item in key_pool:
        if item["key"] == key:
            item["ban_until"] = datetime.now() + timedelta(seconds=ban_duration)
            item["failures"] += 1
            print(f"[KEY] Ключ {key[:10]}... заблокирован на {ban_duration} сек (всего ошибок: {item['failures']})", flush=True)
            break

PROMPT_TEMPLATE = """
Ты — система анализа сообщений из Telegram на предмет оппозиционной, экстремистской или антиправительственной риторики.  
Оцени следующее сообщение и верни ТОЛЬКО JSON с полями:  
- "dangerous": true/false  
- "reason": краткое пояснение на русском, почему опасно или не опасно.  

Сообщение:  
"""

def extract_json(raw):
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    return None

def analyze_message(text, msg_id):
    if not text or len(text) < 10:
        return (False, "слишком короткое или пустое")

    for attempt in range(MAX_RETRIES):
        api_key = get_next_api_key()
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Ты помощник для модерации контента."},
                    {"role": "user", "content": PROMPT_TEMPLATE + text}
                ],
                temperature=0.1,
                extra_headers={
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "Telegram Analyzer",
                },
            )
            raw = response.choices[0].message.content
            if raw is None:
                raise ValueError("Модель вернула None")

            result = extract_json(raw)
            if result is None:
                raise ValueError(f"Невалидный JSON: {raw[:150]}")

            return (result.get("dangerous", False), result.get("reason", "нет пояснения"))

        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = "429" in error_str or "rate limit" in error_str
            if is_rate_limit:
                ban_seconds = 3600
                if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                    retry_after = e.response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            ban_seconds = int(retry_after)
                        except:
                            pass
                if ban_seconds == 3600:
                    match = re.search(r'retry after (\d+)', error_str)
                    if match:
                        ban_seconds = int(match.group(1))
                if ban_seconds < 10:
                    ban_seconds = 60
                mark_key_failed(api_key, ban_duration=ban_seconds)
                print(f"[RATE-LIMIT] Ключ {api_key[:10]}... получил 429, заблокирован на {ban_seconds} сек. Попытка {attempt+1}/{MAX_RETRIES}", flush=True)
                continue
            else:
                mark_key_failed(api_key, ban_duration=30)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1.5 ** attempt)
                    continue
                else:
                    return (False, f"ошибка после {MAX_RETRIES} попыток: {str(e)}")

    return (False, "неизвестная ошибка")

def parse_html(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml")
    rows = []
    tbody = soup.find("tbody")
    if not tbody:
        return rows
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue
        date = tds[1].get_text(strip=True)
        msg_id = tds[2].get_text(strip=True)
        group_td = tds[6]
        group_div = group_td.find("div", class_="channel-card")
        group_id = ""
        if group_div:
            ch_id_span = group_div.find("span", class_="ch-id")
            if ch_id_span:
                group_id = ch_id_span.get_text(strip=True)
        text = tds[7].get_text(strip=True)
        if text:
            rows.append({
                "file": os.path.basename(file_path),
                "date": date,
                "msg_id": msg_id,
                "group_id": group_id,
                "text": text,
            })
    return rows

def parse_all_html():
    all_messages = []
    for root, dirs, files in os.walk(FOLDER):
        for file in files:
            if file.endswith(".html"):
                filepath = os.path.join(root, file)
                print(f"[FILE] Парсинг {os.path.basename(filepath)}...")
                all_messages.extend(parse_html(filepath))
    return all_messages

def load_or_parse_messages():
    if not FORCE_PARSE and os.path.exists(CACHE_FILE):
        print(f"[CACHE] Загружаем сообщения из кеша ({CACHE_FILE})...")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        if FORCE_PARSE:
            print("[FORCE] Принудительный режим: игнорируем кеш и парсим заново.")
        messages = parse_all_html()
        print(f"[SAVE] Сохраняем сообщения в кеш ({CACHE_FILE})...")
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        return messages

# Файл прогресса
PROGRESS_FILE = "progress.json"

def load_progress():
    if RESUME and os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f:
                prog = json.load(f)
                return prog.get("last_index", 0), prog.get("processed_ids", set())
        except:
            return 0, set()
    return 0, set()

def save_progress(last_index, processed_ids):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"last_index": last_index, "processed_ids": list(processed_ids)}, f)

# Глобальная блокировка для записи в CSV
csv_lock = threading.Lock()
csv_writer = None
csv_file = None

def init_csv():
    global csv_writer, csv_file
    # Определяем режим: если RESUME и файл существует, то дозаписываем, иначе перезаписываем
    mode = 'a' if RESUME and os.path.exists(OUTPUT_CSV) else 'w'
    csv_file = open(OUTPUT_CSV, mode, newline="", encoding="utf-8-sig")
    fieldnames = ["file", "date", "msg_id", "group_id", "dangerous", "reason", "text"]
    csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    if mode == 'w':
        csv_writer.writeheader()
    csv_file.flush()

def close_csv():
    global csv_file
    if csv_file:
        csv_file.close()

def write_result(result):
    with csv_lock:
        csv_writer.writerow(result)
        csv_file.flush()

def process_single_message(msg, idx, total, processed_ids):
    # Пропускаем уже обработанные (по msg_id)
    msg_id = msg["msg_id"]
    if msg_id in processed_ids:
        return None
    dangerous, reason = analyze_message(msg["text"], msg_id)
    symbol = "⚠️ ОПАСНО" if dangerous else "✅ Безопасно"
    reason = reason.strip().replace("\n", " ").replace("\r", " ")
    print(f"[{idx}/{total}] {symbol} | {reason}", flush=True)

    if dangerous:
        row = {**msg, "dangerous": dangerous, "reason": reason}
        write_result(row)
    # Добавляем в обработанные (даже безопасные, чтобы не перепроверять)
    processed_ids.add(msg_id)
    return (idx, dangerous)

def main():
    global csv_writer, csv_file
    init_csv()

    all_messages = load_or_parse_messages()
    total = len(all_messages)
    print(f"\n[STATS] Всего сообщений: {total}\n")

    # Загружаем прогресс
    start_index, processed_ids = load_progress()
    if start_index > 0:
        print(f"[RESUME] Продолжаем с индекса {start_index+1} (уже обработано {len(processed_ids)} сообщений)")

    interrupted = False

    def signal_handler(sig, frame):
        nonlocal interrupted
        print("\n[STOP] Получен сигнал остановки, завершаем обработку...", flush=True)
        interrupted = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Планируем задачи только для необработанных сообщений
    pending = [(idx, msg) for idx, msg in enumerate(all_messages, 1) if idx > start_index and msg["msg_id"] not in processed_ids]
    if not pending:
        print("[INFO] Все сообщения уже обработаны.")
        close_csv()
        return

    print(f"[INFO] Осталось обработать: {len(pending)} сообщений")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for idx, msg in pending:
            if interrupted:
                break
            future = executor.submit(process_single_message, msg, idx, total, processed_ids.copy())  # copy для потокобезопасности
            futures[future] = idx

        for future in as_completed(futures):
            if interrupted:
                executor.shutdown(wait=False)
                break
            try:
                result = future.result()
                if result:
                    last_idx, _ = result
                    # Сохраняем прогресс после каждого успешного сообщения
                    save_progress(last_idx, processed_ids)
            except Exception as e:
                print(f"[ERROR] Критическая ошибка при обработке: {e}", flush=True)

        if interrupted:
            executor.shutdown(wait=True)
            # Сохраняем прогресс перед выходом
            if futures:
                last_done = max(futures.values())  # не совсем точно, но приблизительно
                save_progress(last_done, processed_ids)

    # Финальное сохранение прогресса
    save_progress(total, processed_ids)

    # Подсчёт опасных сообщений
    try:
        with open(OUTPUT_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            dangerous_count = sum(1 for row in reader if row.get("dangerous") == "True")
        print(f"\n[STATS] Найдено опасных сообщений: {dangerous_count}")
    except Exception as e:
        print(f"[WARN] Не удалось подсчитать опасные сообщения: {e}")

    close_csv()
    print("[INFO] CSV-файл закрыт. Программа завершена.")

if __name__ == "__main__":
    main()