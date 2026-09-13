"""
Urgency/severity detection via keyword lexicon (FR + AR).

There's no good pretrained "news urgency" classifier to reach for, and
for this kind of signal a curated lexicon is arguably better anyway:
it's transparent (you can see exactly why an article was flagged
urgent), free, instant, and easy for you to tune as you see real
output. Runs on title + optionally body; title match wins (news
outlets front-load severity in the headline).

Tiering:
  - URGENT:  death/casualties, explosions, terrorism, major disasters,
             evacuations, drownings/shipwrecks, earthquakes
  - MODERATE: strikes, protests, accidents, arrests, pollution
              incidents, school/course suspensions, water/power cuts
  - ROUTINE: everything else (investment announcements, tourism stats,
             cultural events, routine administrative news, etc.)
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from analysis.text_utils import strip_diacritics as _strip_diacritics

URGENT_KEYWORDS_FR = [
    "mort", "morte", "morts", "décès", "décédé", "tué", "tuée", "tués",
    "explosion", "explose", "attentat", "terroriste", "terrorisme",
    "catastrophe", "victime", "victimes", "noyade", "naufrage",
    "disparition", "disparus", "séisme", "tremblement de terre",
    "évacuation", "évacuées", "urgence", "alerte rouge", "incendie",
    "blessé grave", "blessés graves", "chavire", "chaviré",
]
URGENT_KEYWORDS_AR = [
    "وفاة", "توفي", "قتيل", "قتلى", "قتل", "انفجار", "ارهابي", "ارهاب",
    "كارثة", "ضحية", "ضحايا", "غرق", "غرقى", "فقدان", "مفقود", "زلزال",
    "اخلاء", "طوارئ", "انذار احمر", "حريق", "جريح خطير",
]

MODERATE_KEYWORDS_FR = [
    "grève", "manifestation", "manifestants", "protestation", "accident",
    "arrestation", "arrêté", "procès", "pollution", "suspension des cours",
    "coupure", "pénurie", "contestent", "rejettent", "exige", "exigent",
    "appelle à", "appellent à",
]
MODERATE_KEYWORDS_AR = [
    "اضراب", "احتجاج", "احتجاجات", "متظاهرون", "حادث", "توقيف", "اعتقال",
    "محاكمة", "تلوث", "ايقاف الدروس", "انقطاع", "نقص", "يطالبون", "يرفضون",
]


def _normalize(text: str) -> str:
    return _strip_diacritics((text or "").lower())


def _find_keyword_matches(text_norm: str, keywords: list[str]) -> list[str]:
    found = []
    for kw in keywords:
        kw_norm = _normalize(kw)
        pattern = r"(?<!\w)" + re.escape(kw_norm) + r"(?!\w)"
        if re.search(pattern, text_norm):
            found.append(kw)
    return found


_URGENT_ALL = URGENT_KEYWORDS_FR + URGENT_KEYWORDS_AR
_MODERATE_ALL = MODERATE_KEYWORDS_FR + MODERATE_KEYWORDS_AR


@dataclass
class UrgencyResult:
    urgency: str = "routine"       # "urgent" | "moderate" | "routine"
    score: float = 0.0             # 0.0-1.0, roughly proportional to matched-keyword weight
    signals: list[str] = field(default_factory=list)


def detect_urgency(title: str, body: str = "") -> UrgencyResult:
    # Title carries most of the signal; body adds supporting evidence
    # but shouldn't override a calm title on its own (e.g. a routine
    # article that quotes someone using an unrelated urgent-sounding word).
    title_norm = _normalize(title)
    body_norm = _normalize(body) if body else ""

    title_urgent = _find_keyword_matches(title_norm, _URGENT_ALL)
    title_moderate = _find_keyword_matches(title_norm, _MODERATE_ALL)

    if title_urgent:
        score = min(1.0, 0.7 + 0.1 * len(title_urgent))
        return UrgencyResult(urgency="urgent", score=score, signals=title_urgent)

    if title_moderate:
        score = min(0.7, 0.4 + 0.1 * len(title_moderate))
        return UrgencyResult(urgency="moderate", score=score, signals=title_moderate)

    if body_norm:
        body_urgent = _find_keyword_matches(body_norm, _URGENT_ALL)
        if body_urgent:
            return UrgencyResult(urgency="urgent", score=0.6, signals=body_urgent)

        body_moderate = _find_keyword_matches(body_norm, _MODERATE_ALL)
        if body_moderate:
            return UrgencyResult(urgency="moderate", score=0.3, signals=body_moderate)

    return UrgencyResult()
