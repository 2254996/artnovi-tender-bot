import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


CHECK_INTERVAL_SECONDS = 21600  # 6 hours


SOURCES = [
    {"name": "Dubai eSupply", "url": "https://esupply.dubai.gov.ae"},
    {"name": "Abu Dhabi Government Procurement", "url": "https://www.adgpg.gov.ae"},
    {"name": "UAE Federal Procurement", "url": "https://procurement.gov.ae"},
    {"name": "Dubai Municipality", "url": "https://www.dm.gov.ae/municipality-business/tenders-biddings/"},
    {"name": "DEWA Tenders", "url": "https://www.dewa.gov.ae/en/about-us/strategy-excellence/tenders"},
    {"name": "RTA Dubai", "url": "https://www.rta.ae/wps/portal/rta/ae/home/about-rta/procurement"},
    {"name": "ADNOC Procurement", "url": "https://www.adnoc.ae/en/suppliers"},
    {"name": "Dubai Culture", "url": "https://dubaiculture.gov.ae"},
    {"name": "Expo City Dubai", "url": "https://www.expocitydubai.com"},
    {"name": "Dubai Future Foundation", "url": "https://www.dubaifuture.ae"},
    {"name": "Dubai Holding", "url": "https://www.dubaiholding.com"},
    {"name": "Miral", "url": "https://www.miral.ae"},
    {"name": "DCT Abu Dhabi", "url": "https://dct.gov.ae"},
    {"name": "Dubai Airports", "url": "https://www.dubaiairports.ae"},
    {"name": "Mubadala", "url": "https://www.mubadala.com"},
    {"name": "Expo Centre Sharjah", "url": "https://www.expocentre.ae"},
    {"name": "Sharjah Museums Authority", "url": "https://www.sharjahmuseums.ae"},
    {"name": "Ajman Government", "url": "https://www.ajman.ae"},
    {"name": "RAK Government", "url": "https://www.rak.ae"},
    {"name": "Fujairah Government", "url": "https://www.fujairah.ae"},
]


LINK_KEYWORDS = [
    "tender", "tenders", "rfp", "rfq", "procurement", "bid",
    "bidding", "opportunity", "opportunities", "supplier", "vendors"
]


ARTNOVI_HIGH = [
    "museum", "visitor center", "visitor centre", "immersive",
    "interactive", "projection mapping", "multimedia", "experience center",
    "national day", "uae national day", "eid al etihad", "union day",
    "opening ceremony", "closing ceremony", "show production",
    "cultural festival", "heritage", "pavilion", "exhibition"
]


ARTNOVI_MEDIUM = [
    "event", "events", "festival", "ceremony", "launch event",
    "audio visual", "av", "led", "led screen", "digital screen",
    "digital signage", "content production", "creative services",
    "animation", "cg", "hologram", "storytelling", "innovation", "future"
]


NEGATIVE = [
    "cleaning", "pest control", "vehicle", "vehicles", "furniture",
    "construction", "maintenance", "security guard", "landscaping",
    "catering", "uniform", "stationery", "insurance"
]


def send_telegram(message):
    if not TOKEN or not CHAT_ID:
        print("Telegram token or chat id is missing")
        return

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True
        },
        timeout=20
    )


def fetch(url):
    response = requests.get(
        url,
        timeout=25,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    response.raise_for_status()
    return response.text


def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_title(soup, fallback):
    if soup.title and soup.title.string:
        return clean_text(soup.title.string)[:160]

    h1 = soup.find("h1")
    if h1:
        return clean_text(h1.get_text())[:160]

    return fallback


def extract_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = clean_text(a.get_text(" ")).lower()
        full_url = urljoin(base_url, href)
        link_text = (href + " " + text).lower()

        if any(word in link_text for word in LINK_KEYWORDS):
            links.add(full_url)

    return list(links)[:15]


def make_description(text):
    text = clean_text(text)
    if len(text) > 700:
        text = text[:700] + "..."
    return text


def score_tender(text):
    low = text.lower()

    high_found = [w for w in ARTNOVI_HIGH if w in low]
    medium_found = [w for w in ARTNOVI_MEDIUM if w in low]
    negative_found = [w for w in NEGATIVE if w in low]

    score = 0
    score += len(high_found) * 2
    score += len(medium_found)
    score -= len(negative_found) * 2

    score = max(0, min(10, score))

    if high_found:
        fit = "HIGH"
    elif medium_found:
        fit = "MEDIUM"
    else:
        fit = "LOW"

    return score, fit, high_found, medium_found, negative_found


def check_page(source_name, url):
    try:
        html = fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        page_title = get_title(soup, source_name)
        page_text = soup.get_text(" ")
        description = make_description(page_text)
        score, fit, high, medium, negative = score_tender(page_text)

        if score >= 3:
            message = f"""🎯 Possible Tender / Opportunity for Artnovi

Source: {source_name}

Title:
{page_title}

Fit Score:
{score}/10 — {fit}

Why relevant:
{", ".join((high + medium)[:12]) if (high or medium) else "General tender/procurement page"}

Short description:
{description}

Direct link:
{url}
"""
            send_telegram(message)

    except Exception as e:
        send_telegram(f"⚠️ Error checking {source_name}: {e}")


def check_source(source):
    try:
        html = fetch(source["url"])
        links = extract_links(source["url"], html)

        check_page(source["name"], source["url"])

        for link in links:
            parsed = urlparse(link)
            if parsed.scheme in ["http", "https"]:
                check_page(source["name"], link)

        print(f"Checked {source['name']} — {len(links)} links")

    except Exception as e:
        send_telegram(f"⚠️ Source error {source['name']}: {e}")


def main():
    send_telegram("🚀 Artnovi Tender Bot started. Checking UAE tender sources...")

    for source in SOURCES:
        check_source(source)

    send_telegram("✅ Tender check completed.")


if __name__ == "__main__":
    while True:
        main()
        time.sleep(CHECK_INTERVAL_SECONDS)
