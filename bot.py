import time
import os
import requests
from bs4 import BeautifulSoup

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

KEYWORDS = [
    "event",
    "events",
    "festival",
    "ceremony",
    "opening ceremony",
    "closing ceremony",
    "inauguration",
    "launch event",

    "national day",
    "uae national day",
    "eid al etihad",
    "union day",

    "museum",
    "visitor center",
    "visitor centre",
    "heritage",
    "cultural",

    "immersive",
    "interactive",
    "experience",
    "experience center",

    "multimedia",
    "projection",
    "projection mapping",
    "3d mapping",

    "audio visual",
    "av",

    "led",
    "led screen",
    "digital screen",
    "digital signage",

    "content production",
    "show production",

    "creative",
    "creative services",

    "animation",
    "cg",
    "hologram",

    "exhibition",
    "expo",
    "pavilion",

    "storytelling",
    "cultural event",
    "cultural festival",

    "innovation",
    "future",

    "rfp",
    "rfq",
    "tender",
    "procurement",
    "bid",
    "opportunity"
]
]

SOURCES = [
      {
        "name": "Dubai eSupply",
        "url": "https://esupply.dubai.gov.ae"
    },
    {
        "name": "Abu Dhabi Government Procurement",
        "url": "https://www.adgpg.gov.ae"
    },
    {
        "name": "Federal Procurement UAE",
        "url": "https://procurement.gov.ae"
    },
    {
        "name": "Expo City Dubai",
        "url": "https://www.expocitydubai.com"
    },
    {
        "name": "Dubai Future Foundation",
        "url": "https://www.dubaifuture.ae"
    },
    {
        "name": "Dubai Holding",
        "url": "https://www.dubaiholding.com"
    },
    {
        "name": "Miral",
        "url": "https://www.miral.ae"
    },
    {
        "name": "Department of Culture and Tourism Abu Dhabi",
        "url": "https://dct.gov.ae"
    },
    {
        "name": "Dubai Airports",
        "url": "https://www.dubaiairports.ae"
    },
    {
        "name": "Mubadala",
        "url": "https://www.mubadala.com"
    },
    {
        "name": "Expo Centre Sharjah",
        "url": "https://www.expocentre.ae"
    },
    {
        "name": "Sharjah Museums Authority",
        "url": "https://www.sharjahmuseums.ae"
    },
    {
        "name": "Ajman Government",
        "url": "https://www.ajman.ae"
    },
    {
        "name": "RAK Government",
        "url": "https://www.rak.ae"
    },
    {
        "name": "Fujairah Government",
        "url": "https://www.fujairah.ae"
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
    while True:
        main()
        time.sleep(21600)  # каждые 6 часов 
