"""
Отладочный скрипт — открывает Kwork, делает скриншот и сохраняет HTML.
Запусти: python debug_kwork.py
Потом скинь мне файлы debug_screenshot.png и debug_page.html
"""

import time
import os

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("❌ pip install selenium webdriver-manager")
    exit(1)


def main():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    print("🌐 Запускаю Chrome...")
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        driver = webdriver.Chrome(options=options)

    urls_to_test = [
        "https://kwork.ru/projects?c=41",
        "https://kwork.ru/projects?keyword=telegram+%D0%B1%D0%BE%D1%82",
    ]

    for i, url in enumerate(urls_to_test):
        print(f"\n{'='*50}")
        print(f"🔍 Загружаю: {url}")
        
        try:
            driver.get(url)
            
            # Ждём подольше — дадим JS отрендерить
            print("   Жду 5 сек для загрузки JS...")
            time.sleep(5)
            
            # Скроллим вниз чтобы подгрузился контент
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(2)
            
            # Скриншот
            screenshot_name = f"debug_screenshot_{i+1}.png"
            driver.save_screenshot(screenshot_name)
            print(f"   📸 Скриншот: {screenshot_name}")
            
            # HTML
            html_name = f"debug_page_{i+1}.html"
            with open(html_name, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
            html_size = os.path.getsize(html_name)
            print(f"   📄 HTML: {html_name} ({html_size // 1024} KB)")
            
            # Быстрый анализ
            source = driver.page_source
            
            # Ищем разные паттерны
            patterns = {
                'href="/projects/': source.count('href="/projects/'),
                "want-card": source.count("want-card"),
                "wants-card": source.count("wants-card"),
                "project-item": source.count("project-item"),
                "card__header": source.count("card__header"),
                "kw-project": source.count("kw-project"),
                "data-id": source.count("data-id"),
                "Предложений": source.count("Предложений"),
                "₽": source.count("₽"),
                "/projects/": source.count("/projects/"),
            }
            
            print("\n   📊 Найдено на странице:")
            for pattern, count in patterns.items():
                marker = "✅" if count > 0 else "❌"
                print(f"      {marker} '{pattern}': {count}")
            
            # Ищем все уникальные ссылки на проекты
            import re
            project_urls = set(re.findall(r'/projects/(\d+)', source))
            print(f"\n   🔗 Уникальных ID проектов: {len(project_urls)}")
            if project_urls:
                print(f"      Примеры: {list(project_urls)[:5]}")
            
            # Ищем все CSS классы с "want" или "project" или "card"
            classes = set(re.findall(r'class="([^"]*(?:want|project|card)[^"]*)"', source, re.I))
            if classes:
                print(f"\n   🎨 Найденные CSS классы:")
                for cls in list(classes)[:15]:
                    print(f"      - {cls[:80]}")
            
            # Проверяем, есть ли Vue/React данные
            if "__NUXT__" in source or "__NEXT_DATA__" in source:
                print("\n   ⚡ Найдены данные SSR (Nuxt/Next)")
            if "window.__" in source:
                # Ищем глобальные переменные
                globals_found = re.findall(r'window\.(__\w+)', source)
                if globals_found:
                    print(f"\n   ⚡ Глобальные JS переменные: {set(globals_found)}")
            
            # Текущий URL (мог быть редирект)
            print(f"\n   🔗 Текущий URL: {driver.current_url}")
            print(f"   📏 Заголовок: {driver.title}")
            
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")

    driver.quit()
    print(f"\n{'='*50}")
    print("✅ Готово! Скинь мне файлы debug_screenshot_*.png")
    print("   Они в папке:", os.getcwd())


if __name__ == "__main__":
    main()
