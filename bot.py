import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timezone

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CHECK_INTERVAL_SECONDS = 21600
SEEN_FILE = "seen_tenders.json"

SOURCES = [
    {"name": "Dubai eSupply", "url": "https://esupply.dubai.gov.ae"},
    {"name": "Abu Dhabi Government Procurement", "url": "https://www.adgpg.gov.ae/en/For-Suppliers/Public-Tenders"},
    {"name": "UAE Federal Procurement", "url": "https://procurement.gov.ae"},
    {"name": "Dubai Municipality", "url": "https://www.dm.gov.ae/municipality-business/tenders-biddings/"},
    {"name": "DEWA Tenders", "url": "https://www.dewa.gov.ae/en/about-us/strategy-excellence/tenders"},
    {"name": "RTA Dubai", "url": "https://www.rta.ae/wps/portal/rta/ae/home/about-rta/procurement"},
    {"name": "Dubai Culture", "url": "https://dubaiculture.gov.ae"},
    {"name": "Expo City Dubai", "url": "https://www.expocitydubai.com"},
    {"name": "Dubai Future Foundation", "url": "https://www.dubaifuture.ae"},
    {"name": "Miral", "url": "https://www.miral.ae"},
    {"name": "DCT Abu Dhabi", "url": "https://dct.gov.ae"},
]

LINK_KEYWORDS = [
    "tender", "rfp", "rfq", "rfi", "eoi", "procurement",
    "bid", "bidding", "opportunity", "proposal", "quotation"
]

HIGH_PRIORITY = [
    "national day", "uae national day", "eid al etihad", "union day",
    "opening ceremony", "closing ceremony", "inauguration",
    "show production", "museum", "visitor center", "visitor centre",
    "immersive", "interactive", "projection mapping", "multimedia",
    "heritage", "exhibition", "pavilion", "experience center"
]

MEDIUM_PRIORITY = [
    "event", "festival", "ceremony", "activation",
    "audio visual", "audiovisual", "led screen", "digital screen",
    "digital signage", "content production", "creative services",
    "animation", "hologram", "storytelling"
]

BAD_WORDS = [
    "closed", "expired", "awarded", "cancelled", "canceled",
    "archived", "archive", "completed", "old tender",
    "accessibility", "privacy policy", "terms", "faq",
    "copyright", "disclaimer", "login", "sign in", "contact us",
    "careers", "abbreviations"
]

NEGATIVE_BUSINESS = [
    "cleaning", "pest control", "vehicle", "furniture",
    "construction", "maintenance", "security guard",
    "landscaping", "catering", "uniform", "stationery",
    "insurance", "medical supplies", "food supply",
    "facility management", "waste management"
]


def send_telegram(message):
    if not TOKEN or not CHAT_ID:
        print("Missing Telegram credentials")
        return

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message[:3900],
            "disable_web_page_preview": True
        },
        timeout=20
    )


def fetch(url):
    r = requests.get(
        url,
        timeout=25,
        headers={"User-Agent": "Mozilla/5.0 ArtnoviTenderBot/3.0"}
    )
    r.raise_for_status()
    return r.text


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
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False, indent=2)


def extract_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = clean_text(a.get_text(" "))
        combined = f"{href} {text}".lower()
        full_url = urljoin(base_url, href)

        if not full_url.startswith("http"):
            continue

        if any(bad in combined for bad in BAD_WORDS):
            continue

        if any(k in combined for k in LINK_KEYWORDS):
            links.add(full_url)

    return list(links)[:40]


def get_title(soup, fallback):
    h1 = soup.find("h1")
    if h1 and clean_text(h1.get_text()):
        return clean_text(h1.get_text())[:160]

    if soup.title and soup.title.string:
        return clean_text(soup.title.string)[:160]

    return fallback


def find_deadline(text):
    patterns = [
        r"(submission deadline|closing date|deadline|last date|bid closing|tender closing|end date)[:\s\-]*([A-Za-z0-9,\-/ ]{6,40})",
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})",
    ]

    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            if len(m.groups()) >= 2:
                return clean_text(m.group(2))
            return clean_text(m.group(1))

    return None


def parse_date(date_text):
    if not date_text:
        return None

    date_text = clean_text(date_text)
    date_text = date_text.replace(",", "")

    formats = [
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_text[:20], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass

    return None


def is_current_tender(text):
    low = text.lower()
    current_year = datetime.now(timezone.utc).year

    if any(bad in low for bad in BAD_WORDS):
        return False, "closed/archive/service page"

    old_years = [str(y) for y in range(2010, current_year)]
    if any(y in low for y in old_years):
        deadline_text = find_deadline(text)
        deadline_date = parse_date(deadline_text)
        if not deadline_date or deadline_date < datetime.now(timezone.utc):
            return False, "old year / expired"

    deadline_text = find_deadline(text)
    deadline_date = parse_date(deadline_text)

    if deadline_date:
        if deadline_date < datetime.now(timezone.utc):
            return False, f"expired deadline {deadline_text}"
        return True, deadline_text

    open_words = ["open", "active", "current tender", "public tender", "submit proposal", "invitation to tender"]
    if any(w in low for w in open_words):
        return True, "Open / active, deadline not found"

    return False, "no future deadline or active status"


def score_tender(text):
    low = text.lower()

    high = [w for w in HIGH_PRIORITY if w in low]
    medium = [w for w in MEDIUM_PRIORITY if w in low]
    negative = [w for w in NEGATIVE_BUSINESS if w in low]

    score = len(high) * 2 + len(medium) - len(negative) * 2
    score = max(0, min(10, score))

    if score >= 8:
        fit = "HIGH"
    elif score >= 5:
        fit = "MEDIUM"
    elif score >= 3:
        fit = "LOW"
    else:
        fit = "VERY LOW"

    return score, fit, high, medium


def classify_category(text):
    low = text.lower()

    if "national day" in low or "eid al etihad" in low or "union day" in low:
        return "🇦🇪 NATIONAL DAY"
    if "opening ceremony" in low or "closing ceremony" in low or "inauguration" in low:
        return "🎭 CEREMONY / SHOW"
    if "museum" in low or "heritage" in low or "visitor center" in low or "visitor centre" in low:
        return "🏛 MUSEUM / HERITAGE"
    if "immersive" in low or "interactive" in low or "experience center" in low:
        return "✨ IMMERSIVE / INTERACTIVE"
    if "led screen" in low or "digital screen" in low or "audio visual" in low:
        return "📺 AV / LED / DIGITAL"
    if "event" in low or "festival" in low:
        return "🎪 EVENT / FESTIVAL"

    return "📌 GENERAL"


def short_description(text):
    text = clean_text(text)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    selected = []
    for s in sentences:
        low = s.lower()
        if any(w in low for w in HIGH_PRIORITY + MEDIUM_PRIORITY + LINK_KEYWORDS):
            selected.append(s)

    if selected:
        return clean_text(" ".join(selected[:3]))[:700]

    return text[:700]


def check_page(source_name, url, seen):
    if url in seen:
        return "seen"

    try:
        html = fetch(url)
        soup = BeautifulSoup(html, "html.parser")
        title = get_title(soup, source_name)
        text = soup.get_text(" ")

        current, deadline = is_current_tender(text)
        if not current:
            return f"skipped: {deadline}"

        score, fit, high, medium = score_tender(text)
        if score < 3:
            return "skipped: low score"

        category = classify_category(text)
        description = short_description(text)
        matched = ", ".join((high + medium)[:10]) or "general tender match"

        message = f"""🎯 NEW ACTIVE TENDER / OPPORTUNITY

Source:
{source_name}

Category:
{category}

Title:
{title}

Artnovi Fit:
{score}/10 — {fit}

Deadline / Status:
{deadline}

Why relevant:
{matched}

Short description:
{description}

Direct link:
{url}
"""
        send_telegram(message)
        seen.add(url)
        return "sent"

    except Exception as e:
        return f"error: {e}"


def check_source(source, seen):
    try:
        html = fetch(source["url"])
        links = extract_links(source["url"], html)

        sent = 0
        skipped = 0

        for link in links:
            result = check_page(source["name"], link, seen)
            if result == "sent":
                sent += 1
            else:
                skipped += 1

        print(f"{source['name']}: links={len(links)}, sent={sent}, skipped={skipped}")
        return len(links), sent, skipped

    except Exception as e:
        print(f"Source error {source['name']}: {e}")
        return 0, 0, 1


def main():
    send_telegram("🚀 Artnovi Tender Bot v3 started. Checking ACTIVE UAE tenders...")

    seen = load_seen()

    total_links = 0
    total_sent = 0
    total_skipped = 0

    for source in SOURCES:
        links, sent, skipped = check_source(source, seen)
        total_links += links
        total_sent += sent
        total_skipped += skipped

    save_seen(seen)

    send_telegram(
        f"✅ Tender check completed.\n\n"
        f"Links checked: {total_links}\n"
        f"New active tenders sent: {total_sent}\n"
        f"Skipped old/closed/irrelevant: {total_skipped}\n"
        f"Total saved seen links: {len(seen)}"
    )


if __name__ == "__main__":
    while True:
        main()
        time.sleep(CHECK_INTERVAL_SECONDS)
