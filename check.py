import os
import sys
import json
import csv
import time
import re
import argparse
from bs4 import BeautifulSoup
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

FOLDER = "./html_reports"
OUTPUT_CSV = "dangerous_openrouter.csv"
CACHE_FILE = "parsed_messages.json"
OPENROUTER_API_KEY = None
MAX_WORKERS = 5
MAX_RETRIES = 3
FORCE_PARSE = False
MODEL = "openrouter/owl-alpha"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Анализ Telegram-сообщений через OpenRouter"
    )
    parser.add_argument(
        "--folder", default="./html_reports", help="Папка с HTML-файлами"
    )
    parser.add_argument(
        "--cache",
        default="parsed_messages.json",
        help="Файл кеша распарсенных сообщений",
    )
    parser.add_argument(
        "--output", default="dangerous_openrouter.csv", help="Выходной CSV-файл"
    )
    parser.add_argument("--api-key", required=True, help="API-ключ OpenRouter")
    parser.add_argument("--model", default="openrouter/owl-alpha", help="Имя модели")
    parser.add_argument(
        "--max-workers", type=int, default=5, help="Количество параллельных потоков"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Количество повторных попыток при ошибке",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительно перепарсить HTML (игнорировать кеш)",
    )
    return parser.parse_args()


args = parse_args()

FOLDER = args.folder
CACHE_FILE = args.cache
OUTPUT_CSV = args.output
OPENROUTER_API_KEY = args.api_key
MODEL = args.model
MAX_WORKERS = args.max_workers
MAX_RETRIES = args.max_retries
FORCE_PARSE = args.force

client = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")

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
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты помощник для модерации контента.",
                    },
                    {"role": "user", "content": PROMPT_TEMPLATE + text},
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

            return (
                result.get("dangerous", False),
                result.get("reason", "нет пояснения"),
            )
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1.5**attempt)
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
            rows.append(
                {
                    "file": os.path.basename(file_path),
                    "date": date,
                    "msg_id": msg_id,
                    "group_id": group_id,
                    "text": text,
                }
            )
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


def process_single_message(msg, idx, total):
    dangerous, reason = analyze_message(msg["text"], msg["msg_id"])
    symbol = "⚠️ ОПАСНО" if dangerous else "✅ Безопасно"
    reason = reason.strip().replace("\n", " ").replace("\r", " ")
    print(f"[{idx}/{total}] {symbol} | {reason}", flush=True)
    return {**msg, "dangerous": dangerous, "reason": reason}


def main():
    all_messages = load_or_parse_messages()
    total = len(all_messages)
    print(f"\n[STATS] Всего сообщений: {total}\n")

    results = [None] * total

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for idx, msg in enumerate(all_messages, 1):
            future = executor.submit(process_single_message, msg, idx, total)
            futures[future] = idx

        for future in as_completed(futures):
            try:
                result = future.result()
                results[futures[future] - 1] = result
            except Exception as e:
                print(f"[ERROR] Критическая ошибка: {e}")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "file",
            "date",
            "msg_id",
            "group_id",
            "dangerous",
            "reason",
            "text",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    dangerous_msgs = [r for r in results if r and r["dangerous"]]
    print(f"\n[STATS] Найдено опасных сообщений: {len(dangerous_msgs)}")
    if dangerous_msgs:
        with open("dangerous_only.csv", "w", newline="", encoding="utf-8-sig") as f2:
            writer = csv.DictWriter(f2, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(dangerous_msgs)
        print("[SAVE] Опасные сообщения сохранены в dangerous_only.csv")


if __name__ == "__main__":
    main()
