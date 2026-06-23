import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CHECK_INTERVAL_SECONDS = 21600  # 6 hours
SEEN_FILE = "seen_tenders.json"


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
    "tender", "tenders", "rfp", "rfq", "rfi", "eoi",
    "procurement", "bid", "bidding", "opportunity",
    "opportunities", "supplier", "vendors", "vendor",
    "contract", "contracts", "quotation", "proposal"
]


DOCUMENT_EXTENSIONS = [
    ".pdf", ".doc", ".docx", ".xls", ".xlsx"
]


HIGH_PRIORITY = [
    "national day", "uae national day", "eid al etihad", "union day",
    "opening ceremony", "closing ceremony", "inauguration ceremony",
    "launch ceremony", "show production", "cultural show",
    "heritage show", "immersive show", "projection show",
    "multimedia show", "museum", "visitor center", "visitor centre",
    "experience center", "experience centre", "immersive experience",
    "interactive experience", "projection mapping", "3d mapping",
    "pavilion", "exhibition", "heritage", "storytelling"
]


MEDIUM_PRIORITY = [
    "event", "events", "festival", "ceremony", "activation",
    "audio visual", "audiovisual", "led screen",
    "digital screen", "digital signage", "content production",
    "creative services", "animation", "cg", "hologram",
    "interactive", "immersive", "multimedia", "innovation",
    "future", "visitor experience", "public art"
]


NEGATIVE = [
    "cleaning", "pest control", "vehicle", "vehicles", "furniture",
    "construction", "maintenance", "security guard", "landscaping",
    "catering", "uniform", "stationery", "insurance", "medical supplies",
    "food supply", "facility management", "waste management"
]


DEADLINE_PATTERNS = [
    r"(submission deadline[:\s]+.{0,40})",
    r"(closing date[:\s]+.{0,40})",
    r"(deadline[:\s]+.{0,40})",
    r"(last date[:\s]+.{0,40})",
    r"(bid closing[:\s]+.{0,40})",
    r"(tender closing[:\s]+.{0,40})",
    r"(\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})",
    r"(\d{1,2}/\d{1,2}/\d{4})",
    r"(\d{4}-\d{2}-\d{2})",
]


def send_telegram(message):
    if not TOKEN or not CHAT_ID:
        print("Telegram token or chat id is missing")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": message[:3900],
                "disable_web_page_preview": True
            },
            timeout=20
        )
    except Exception as e:
        print(f"Telegram error: {e}")


def fetch(url):
    response = requests.get(
        url,
        timeout=25,
        headers={
            "User-Agent": "Mozilla/5.0 ArtnoviTenderBot/2.0"
        }
    )
    response.raise_for_status()
    return response.text


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Could not save seen file: {e}")


def is_document_link(url):
    low = url.lower()
    return any(low.endswith(ext) or ext + "?" in low for ext in DOCUMENT_EXTENSIONS)


def looks_like_tender_link(url, text=""):
    combined = f"{url} {text}".lower()

    return (
        any(word in combined for word in LINK_KEYWORDS)
        or is_document_link(url)
    )


def extract_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        label = clean_text(a.get_text(" "))
        full_url = urljoin(base_url, href)

        if not full_url.startswith("http"):
            continue

        if looks_like_tender_link(full_url, label):
            links.add(full_url)

    return list(links)[:30]


def get_title(soup, fallback):
    h1 = soup.find("h1")
    if h1 and clean_text(h1.get_text()):
        return clean_text(h1.get_text())[:160]

    if soup.title and soup.title.string:
        return clean_text(soup.title.string)[:160]

    return fallback[:160]


def find_deadline(text):
    low = text.lower()

    for pattern in DEADLINE_PATTERNS:
        match = re.search(pattern, low, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))[:120]

    return "Not found"


def classify_category(text):
    low = text.lower()

    if any(x in low for x in ["national day", "eid al etihad", "union day"]):
        return "🇦🇪 NATIONAL DAY"
    if any(x in low for x in ["opening ceremony", "closing ceremony", "inauguration"]):
        return "🎭 CEREMONY / SHOW"
    if any(x in low for x in ["museum", "visitor center", "visitor centre", "heritage"]):
        return "🏛 MUSEUM / HERITAGE"
    if any(x in low for x in ["immersive", "interactive", "experience center", "experience centre"]):
        return "✨ IMMERSIVE / INTERACTIVE"
    if any(x in low for x in ["led", "digital screen", "digital signage", "av", "audio visual"]):
        return "📺 AV / LED / DIGITAL"
    if any(x in low for x in ["event", "festival", "activation"]):
        return "🎪 EVENT / FESTIVAL"

    return "📌 GENERAL OPPORTUNITY"


def score_tender(text):
    low = text.lower()

    high_found = [w for w in HIGH_PRIORITY if w in low]
    medium_found = [w for w in MEDIUM_PRIORITY if w in low]
    negative_found = [w for w in NEGATIVE if w in low]

    score = 0
    score += len(high_found) * 2
    score += len(medium_found)
    score -= len(negative_found) * 2

    score = max(0, min(10, score))

    if score >= 8:
        fit = "HIGH"
    elif score >= 5:
        fit = "MEDIUM"
    elif score >= 3:
        fit = "LOW"
    else:
        fit = "VERY LOW"

    return score, fit, high_found, medium_found, negative_found


def short_description(text):
    text = clean_text(text)

    important_sentences = []
    sentences = re.split(r"(?<=[.!?])\s+", text)

    for sentence in sentences:
        low = sentence.lower()
        if any(w in low for w in HIGH_PRIORITY + MEDIUM_PRIORITY + LINK_KEYWORDS):
            important_sentences.append(sentence)

    if important_sentences:
        result = " ".join(important_sentences[:3])
    else:
        result = text[:700]

    return clean_text(result)[:700]


def build_message(source_name, title, url, text):
    score, fit, high, medium, negative = score_tender(text)
    category = classify_category(text)
    deadline = find_deadline(text)
    description = short_description(text)

    matched = high + medium
    matched_text = ", ".join(matched[:12]) if matched else "No strong match"

    message = f"""🎯 NEW TENDER / OPPORTUNITY

Source:
{source_name}

Category:
{category}

Title:
{title}

Artnovi Fit:
{score}/10 — {fit}

Deadline:
{deadline}

Why relevant:
{matched_text}

Short description:
{description}

Direct link:
{url}
"""
    return message, score


def check_document_link(source_name, url, seen):
    if url in seen:
        return

    fake_text = url.replace("-", " ").replace("_", " ").replace("/", " ")
    title = url.split("/")[-1][:160] or source_name

    message, score = build_message(source_name, title, url, fake_text)

    if score >= 3:
        send_telegram(message)
        seen.add(url)


def check_page(source_name, url, seen):
    if url in seen:
        return

    if is_document_link(url):
        check_document_link(source_name, url, seen)
        return

    try:
        html = fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        title = get_title(soup, source_name)
        text = soup.get_text(" ")

        message, score = build_message(source_name, title, url, text)

        if score >= 3:
            send_telegram(message)
            seen.add(url)

    except Exception as e:
        print(f"Error checking page {url}: {e}")


def check_source(source, seen):
    try:
        html = fetch(source["url"])
        links = extract_links(source["url"], html)

        for link in links:
            check_page(source["name"], link, seen)

        print(f"Checked {source['name']} — found {len(links)} possible links")

    except Exception as e:
        print(f"Source error {source['name']}: {e}")


def main():
    send_telegram("🚀 Artnovi Tender Bot v2 started")

    seen = load_seen()

    for source in SOURCES:
        check_source(source, seen)

    save_seen(seen)

    send_telegram("✅ Tender check completed")


if __name__ == "__main__":
    while True:
        main()
        time.sleep(CHECK_INTERVAL_SECONDS)
