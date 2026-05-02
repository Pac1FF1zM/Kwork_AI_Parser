"""
Kwork Auto-Responder — генерирует черновики откликов через Ollama.
Работает вместе с парсером: находит заказ → ИИ пишет отклик → шлёт в Telegram.

Настройка:
1. Установи Ollama: https://ollama.com
2. Скачай модель: ollama pull qwen2.5:7b
3. Настрой TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID
4. Запусти: python kwork_responder.py

Парсер + автоответчик в одном файле.
"""

import requests
import time
import json
import re
import hashlib
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("❌ pip install selenium webdriver-manager requests")
    exit(1)


# ==================== НАСТРОЙКИ ====================

TELEGRAM_BOT_TOKEN = "6813210784:AAFkSDQvZFvTwmhy_O26vfIH7gKs6yimLLc"
TELEGRAM_CHAT_ID = "814326688"


# Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"  # Лучшая модель для русского на 16 ГБ RAM

# Твой профиль — ИИ будет использовать это для генерации откликов
MY_PROFILE = """
Ты откликаешься на вакансии на сайте kworker, вот мой стек:
Я Python-разработчик. Мой стек:
- Telegram-боты: aiogram, pyTelegramBotAPI
- Backend: FastAPI, Django, Django REST Framework
- Базы данных: PostgreSQL, SQLite
- Discord-боты
- REST API, asyncio, aiohttp
- Деплой на VPS, Linux

Я пишу чистый код, соблюдаю сроки, всегда на связи.
Главное Правило - Писать как Человек. Ясно изъясняться, не писать слишком длинный и не слишком короткий отклик, писать по факту
"""

# Ключевые слова
KEYWORDS = [
    "python", "fastapi", "django", "flask",
    "aiogram", "telegram бот", "telegram-бот",
    "телеграм бот", "телеграм-бот", "pytelegrambotapi",
    "discord бот", "discord-бот", "дискорд бот",
    "postgresql", "sqlite", "rest api",
    "бот на python", "парсер python", "скрипт python",
    "asyncio", "aiohttp", "бот",
]

SEARCH_QUERIES = [
    "telegram бот",
    "python бот",
    "fastapi",
    "django",
    "discord бот",
    "парсер python",
    "скрипт python",
    "aiogram",
]

MIN_BUDGET = 1000
CHECK_INTERVAL = 300
SEEN_FILE = "seen_projects.json"


# ==================== УТИЛИТЫ ====================

def load_seen() -> set:
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"   [!] Telegram: {e}")
        return False


def matches_keywords(text: str) -> list:
    text_lower = text.lower()
    found = []
    for kw in KEYWORDS:
        if kw.lower() in text_lower and kw not in found:
            found.append(kw)
    return found


def parse_budget_number(text: str) -> int:
    cleaned = re.sub(r"[^\d]", "", text.replace("\xa0", ""))
    if cleaned.isdigit() and int(cleaned) > 0:
        return int(cleaned)
    return 0


# ==================== OLLAMA ====================

def check_ollama() -> bool:
    """Проверяет, запущен ли Ollama."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            if any(OLLAMA_MODEL.split(":")[0] in m for m in models):
                return True
            else:
                print(f"   ⚠️  Модель {OLLAMA_MODEL} не найдена!")
                print(f"   Доступные: {', '.join(models) if models else 'нет'}")
                print(f"   Скачай: ollama pull {OLLAMA_MODEL}")
                return False
        return False
    except Exception:
        return False


def generate_response(title: str, description: str, budget: str) -> str:
    """Генерирует черновик отклика через Ollama."""

    prompt = f"""Ты — фрилансер, Python-разработчик. Напиши отклик на заказ на бирже Kwork.

Твой профиль:
{MY_PROFILE}

Заказ:
Название: {title}
Описание: {description}
Бюджет: {budget}

Правила:
1. Начни с приветствия
2. Покажи что понял задачу — перефразируй её суть в 1 предложении
3. Кратко опиши как будешь решать (технологии, подход) — 2-3 предложения
4. Упомяни релевантный опыт из профиля
5. Закончи призывом обсудить детали
6. Пиши кратко — максимум 150 слов
7. Не используй шаблонные фразы типа "Я опытный разработчик"
8. Пиши естественно, по-человечески, на русском языке
9. НЕ пиши ничего кроме самого отклика — без пояснений и комментариев"""

    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 500,
            }
        }, timeout=120)  # Таймаут 2 мин — на CPU может быть долго

        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        else:
            print(f"   [!] Ollama ошибка: {resp.status_code}")
            return ""
    except requests.exceptions.Timeout:
        print("   [!] Ollama таймаут — модель генерирует слишком долго")
        return ""
    except Exception as e:
        print(f"   [!] Ollama ошибка: {e}")
        return ""


# ==================== SELENIUM ====================

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver


def parse_page(driver, url: str, source_label: str) -> list:
    """Парсит страницу проектов Kwork."""
    projects = []
    try:
        driver.get(url)
        time.sleep(3)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".want-card"))
            )
        except Exception:
            driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(2)

        cards = driver.find_elements(By.CSS_SELECTOR, ".want-card")

        for card in cards:
            try:
                try:
                    link_el = card.find_element(By.CSS_SELECTOR, "a[href*='/projects/']")
                    title = link_el.text.strip()
                    href = link_el.get_attribute("href")
                except Exception:
                    continue

                if not title or len(title) < 3 or not href:
                    continue

                description = ""
                try:
                    desc_el = card.find_element(By.CSS_SELECTOR, ".wants-card__description-text")
                    description = desc_el.text.strip()
                except Exception:
                    pass

                budget = ""
                try:
                    price_el = card.find_element(By.CSS_SELECTOR, ".wants-card__price")
                    budget = price_el.text.strip()
                except Exception:
                    pass

                if not budget:
                    try:
                        card_text = card.text
                        price_match = re.search(r'(\d[\d\s]*)\s*₽', card_text)
                        if price_match:
                            budget = price_match.group(0).strip()
                    except Exception:
                        pass

                offers = ""
                try:
                    card_text = card.text
                    offers_match = re.search(r'Предложений:\s*(\d+)', card_text)
                    if offers_match:
                        offers = offers_match.group(1)
                except Exception:
                    pass

                projects.append({
                    "title": title,
                    "url": href,
                    "description": description,
                    "budget": budget,
                    "offers": offers,
                    "source": source_label,
                })
            except Exception:
                continue
    except Exception as e:
        print(f"   [!] Ошибка: {e}")

    return projects


# ==================== ФОРМАТИРОВАНИЕ ====================

def format_job_message(project: dict, matched: list) -> str:
    """Сообщение о найденном заказе."""
    msg = f"🔔 <b>Новый заказ!</b>\n\n"
    msg += f"📌 <b>{project['title']}</b>\n\n"

    if project.get("description"):
        desc = project["description"][:300]
        if len(project["description"]) > 300:
            desc += "..."
        msg += f"📝 {desc}\n\n"

    if project.get("budget"):
        msg += f"💰 Бюджет: {project['budget']}\n"
    if project.get("offers"):
        msg += f"👥 Предложений: {project['offers']}\n"

    msg += f"🏷 Совпадения: {', '.join(matched)}\n"
    msg += f"\n🔗 <a href=\"{project['url']}\">Открыть заказ →</a>"
    return msg


def format_draft_message(project: dict, draft: str) -> str:
    """Сообщение с черновиком отклика."""
    msg = f"✏️ <b>Черновик отклика:</b>\n"
    msg += f"📌 {project['title']}\n\n"
    msg += f"<pre>{draft}</pre>\n\n"
    msg += f"👆 Скопируй текст выше и вставь в отклик\n"
    msg += f"🔗 <a href=\"{project['url']}\">Откликнуться →</a>"
    return msg


# ==================== ГЛАВНЫЙ ЦИКЛ ====================

def run():
    print("=" * 55)
    print("🚀 Kwork Parser + Auto-Responder")
    print(f"🤖 Модель: {OLLAMA_MODEL}")
    print(f"🔍 Запросы: {', '.join(SEARCH_QUERIES)}")
    print(f"💰 Мин. бюджет: {MIN_BUDGET}₽")
    print(f"⏰ Интервал: {CHECK_INTERVAL // 60} мин")
    print("=" * 55)

    # Telegram
    if "ВСТАВЬ" in TELEGRAM_BOT_TOKEN or "ВСТАВЬ" in TELEGRAM_CHAT_ID:
        print("\n⚠️  Настрой TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID!")
        tg_ok = False
    else:
        tg_ok = send_telegram("✅ Kwork Parser + AI Responder запущен!")
        print("✅ Telegram подключён!" if tg_ok else "⚠️  Ошибка Telegram")

    # Ollama
    ollama_ok = check_ollama()
    if ollama_ok:
        print(f"✅ Ollama подключена ({OLLAMA_MODEL})")
    else:
        print(f"⚠️  Ollama не найдена — отклики генерироваться не будут")
        print(f"   Запусти Ollama и скачай модель: ollama pull {OLLAMA_MODEL}")

    seen = load_seen()
    print(f"📦 В базе: {len(seen)} заказов\n")

    print("🌐 Запускаю Chrome...")
    try:
        driver = create_driver()
        print("✅ Браузер готов!\n")
    except Exception as e:
        print(f"❌ Chrome: {e}")
        return

    try:
        while True:
            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] 🔍 Проверяю заказы...")

            all_projects = []
            new_count = 0

            # Категории
            for cat_url, label in [
                ("https://kwork.ru/projects?c=41", "Скрипты/боты"),
                ("https://kwork.ru/projects?c=11", "Программирование"),
            ]:
                results = parse_page(driver, cat_url, label)
                all_projects.extend(results)
                print(f"   📂 {label}: {len(results)}")
                time.sleep(2)

            # Поиск
            for query in SEARCH_QUERIES:
                search_url = f"https://kwork.ru/projects?keyword={requests.utils.quote(query)}"
                results = parse_page(driver, search_url, query)
                all_projects.extend(results)
                print(f"   🔎 '{query}': {len(results)}")
                time.sleep(2)

            # Дедупликация
            unique = {}
            for p in all_projects:
                unique[p["url"]] = p

            print(f"   📊 Уникальных: {len(unique)}")

            for url, project in unique.items():
                pid = hashlib.md5(url.encode()).hexdigest()[:12]

                if pid in seen:
                    continue

                text = f"{project['title']} {project.get('description', '')}"
                matched = matches_keywords(text)

                if not matched:
                    seen.add(pid)
                    continue

                budget_num = parse_budget_number(project.get("budget", ""))
                if 0 < budget_num < MIN_BUDGET:
                    seen.add(pid)
                    continue

                # Подходящий заказ!
                new_count += 1
                seen.add(pid)

                print(f"\n   ✅ НОВЫЙ: {project['title']}")
                print(f"      💰 {project.get('budget', '?')}")

                # Отправляем информацию о заказе
                if tg_ok:
                    job_msg = format_job_message(project, matched)
                    send_telegram(job_msg)
                    time.sleep(0.5)

                # Генерируем черновик отклика
                if ollama_ok:
                    print(f"      🤖 Генерирую отклик...")
                    draft = generate_response(
                        title=project["title"],
                        description=project.get("description", ""),
                        budget=project.get("budget", "не указан"),
                    )

                    if draft:
                        print(f"      ✅ Отклик готов ({len(draft)} символов)")
                        if tg_ok:
                            draft_msg = format_draft_message(project, draft)
                            send_telegram(draft_msg)
                    else:
                        print(f"      ⚠️  Не удалось сгенерировать отклик")

                    time.sleep(1)

            save_seen(seen)

            if new_count == 0:
                print("   ✉️  Новых подходящих нет.")
            else:
                print(f"\n   📬 Обработано: {new_count}")

            print(f"   ⏳ Жду {CHECK_INTERVAL // 60} мин...\n")
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑 Стоп!")
    finally:
        driver.quit()
        print("👋 Готово!")


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("Бот остановлен")
