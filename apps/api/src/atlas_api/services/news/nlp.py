"""NER country extraction, relevance keyword gate, rule-based event classification."""

import spacy

_nlp = None

COUNTRY_MAP: dict[str, str] = {
    "Ghana": "GHA", "Kenya": "KEN", "Nigeria": "NGA", "Senegal": "SEN",
    "Ethiopia": "ETH", "Rwanda": "RWA", "South Africa": "ZAF", "Morocco": "MAR",
    "Egypt": "EGY", "Ivory Coast": "CIV", "Côte d'Ivoire": "CIV", "Cote d'Ivoire": "CIV",
}

RELEVANCE_KEYWORDS = {
    "debt", "gdp", "inflation", "imf", "rating", "fiscal", "bond", "eurobond",
    "currency", "exchange rate", "reserve", "deficit", "sovereign", "restructuring",
    "credit", "downgrade", "upgrade", "central bank", "monetary", "budget",
    "trade", "export", "import", "current account", "fdi", "investment",
}

EVENT_RULES: list[tuple[set[str], str]] = [
    ({"imf", "programme", "program", "disbursement", "review"}, "IMF"),
    ({"rating", "downgrade", "upgrade", "credit", "s&p", "moody", "fitch"}, "Rating"),
    ({"interest rate", "central bank", "monetary", "repo rate", "policy rate"}, "Monetary"),
    ({"budget", "fiscal", "tax", "spending", "deficit", "surplus", "revenue"}, "Fiscal"),
    (
        {
            "election", "president", "government", "parliament",
            "coup", "protest", "reform", "sanction",
        },
        "Political",
    ),
    (
        {
            "trade", "export", "import", "tariff",
            "current account", "fdi", "investment", "remittance",
        },
        "External",
    ),
    (
        {"currency", "exchange rate", "depreciation", "devaluation", "dollar", "forex", "reserve"},
        "Market",
    ),
]


def _load_nlp() -> spacy.language.Language:
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def extract_country(title: str, body: str) -> str | None:
    nlp = _load_nlp()
    doc = nlp(title + " " + body[:500])
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC"):
            iso3 = COUNTRY_MAP.get(ent.text)
            if iso3 is not None:
                return iso3
    for name, iso3 in COUNTRY_MAP.items():
        if name.lower() in (title + " " + body).lower():
            return iso3
    return None


def is_relevant(title: str, body: str) -> bool:
    combined = (title + " " + body).lower()
    matches = sum(1 for kw in RELEVANCE_KEYWORDS if kw in combined)
    return matches >= 2


def classify_event(title: str, body: str) -> str:
    combined = (title + " " + body).lower()
    best_type = "Market"
    best_score = 0
    for keywords, event_type in EVENT_RULES:
        score = sum(1 for kw in keywords if kw in combined)
        if score > best_score:
            best_score = score
            best_type = event_type
    return best_type
