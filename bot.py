import os
import requests
from bs4 import BeautifulSoup

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

KEYWORDS = [
    "event", "events", "festival", "ceremony", "opening ceremony",
    "national day", "exhibition", "museum", "visitor center",
    "experience center", "immersive", "interactive", "multimedia",
    "projection", "projection mapping", "audio visual", "av",
    "led", "digital experience", "content production", "creative",
    "media production", "show production", "pavilion", "hologram"
]

SOURCES = [
    {
        "name": "Dubai eSupply",
        "url": "https://esupply.dubai.gov.ae/esop/guest/go/opportunity/current?locale=en"
    },
    {
        "name": "Dubai Municipality",
        "url": "https://www.dm.gov.ae/municipality-business/tenders-biddings/"
    },
    {
        "name": "Expo City Dubai Suppliers",
        "url": "https://www.expocitydubai.com/en/suppliers/"
    },
    {
        "name": "DEWA Tenders",
        "url": "https://www.dewa.gov.ae/en/about-us/strategy-excellence/tenders"
    },
    {
        "name": "RTA Dubai",
        "url": "https://www.rta.ae/wps/portal/rta/ae/home/about-rta/procurement"
    },
    {
        "name": "ADNOC Procurement",
        "url": "https://www.adnoc.ae/en/suppliers"
    },
    {
        "name": "Dubai Culture",
        "url": "https://dubaiculture.gov.ae"
    }
]

def send_telegram(message):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True
        }
    )

def check_source(source):
    try:
        response = requests.get(
            source["url"],
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        text = response.text.lower()
        soup = BeautifulSoup(response.text, "html.parser")
        page_title = soup.title.string.strip() if soup.title else source["name"]

        found = [kw for kw in KEYWORDS if kw.lower() in text]

        if found:
            message = f"""🎯 Возможный тендер / opportunity для Artnovi

Портал: {source['name']}
Страница: {page_title}

Найдены ключевые слова:
{', '.join(found[:10])}

Ссылка:
{source['url']}

Комментарий:
Открой страницу и проверь новые тендеры вручную. На этом этапе бот нашёл совпадение по странице, а не по отдельному тендеру.
"""
            send_telegram(message)

    except Exception as e:
        send_telegram(f"⚠️ Ошибка проверки {source['name']}: {e}")

def main():
    send_telegram("🚀 Artnovi Tender Bot запущен. Начинаю проверку источников ОАЭ.")

    for source in SOURCES:
        check_source(source)

    send_telegram("✅ Проверка завершена.")

if __name__ == "__main__":
    main()
