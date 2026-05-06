import requests
import re
from datetime import date, datetime
from bs4 import BeautifulSoup
from functools import lru_cache

KNOX_CALENDAR_URL = "https://www.knox.edu/academics/academic-calendar"


def fetch_knox_terms():
    response = requests.get(KNOX_CALENDAR_URL, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text("\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    terms = []
    current_term = None
    start_date = None
    end_date = None

    for i, line in enumerate(lines):
        term_match = re.search(r"(Fall|Winter|Spring)\s+Term\s+(\d{4})", line)

        if term_match:
            if current_term and start_date and end_date:
                terms.append({
                    "name": current_term,
                    "start": start_date,
                    "end": end_date,
                })

            season = term_match.group(1)
            year = int(term_match.group(2))
            current_term = f"{season} {year}"
            start_date = None
            end_date = None
            continue

        if current_term:
            year = int(current_term.split()[1])

            if "Residence halls open" in line:
                prev_line = lines[i - 1] if i > 0 else ""
                date_match = re.search(
                    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}",
                    prev_line,
                )
                if date_match:
                    start_date = datetime.strptime(
                        date_match.group(0), "%B %d"
                    ).replace(year=year).date()

            if "Residence halls close" in line and not end_date:
                prev_line = lines[i - 1] if i > 0 else ""
                date_match = re.search(
                    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}",
                    prev_line,
                )
                if date_match:
                    end_date = datetime.strptime(
                        date_match.group(0), "%B %d"
                    ).replace(year=year).date()

    if current_term and start_date and end_date:
        terms.append({
            "name": current_term,
            "start": start_date,
            "end": end_date,
        })

    return terms


@lru_cache(maxsize=1)
def get_cached_terms():
    try:
        terms = fetch_knox_terms()
        if terms:
            return terms
    except Exception:
        pass

    return get_fallback_terms()


def get_fallback_terms():
    return [
        {
            "name": "Winter 2026",
            "start": date(2026, 1, 3),
            "end": date(2026, 3, 16),
        },
        {
            "name": "Spring 2026",
            "start": date(2026, 3, 24),
            "end": date(2026, 6, 3),
        },
        {
            "name": "Fall 2026",
            "start": date(2026, 9, 12),
            "end": date(2026, 11, 23),
        },
    ]


def get_current_knox_term():
    today = date.today()
    terms = get_cached_terms()

    for term in terms:
        if term["start"] <= today <= term["end"]:
            return term["name"]

    return None


def get_current_knox_term_info():
    today = date.today()

    try:
        terms = fetch_knox_terms()
        source = "knox_website" if terms else "fallback"
    except Exception:
        terms = []
        source = "fallback"

    if not terms:
        terms = get_fallback_terms()

    for term in terms:
        if term["start"] <= today <= term["end"]:
            return {
                "term": term["name"],
                "source": source,
                "start": str(term["start"]),
                "end": str(term["end"]),
            }

    return {
        "term": None,
        "source": source,
    }