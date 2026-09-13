"""
Region detection via gazetteer matching.

Strategy (title-primary, body-secondary, per the project's original
requirement):
  1. Search the TITLE for a delegation/city name -> resolve to its
     governorate. This is the highest-confidence signal: from the real
     samples pulled during feasibility testing, Tunisian regional news
     titles almost always lead with the specific town ("Sidi Bouzid :
     un terroriste...", "Gafsa: Déraillement d'un train...").
  2. If no delegation match, search the TITLE for a governorate name
     directly.
  3. If nothing in the title, repeat steps 1-2 on the BODY, at lower
     confidence (a region mentioned only in the body is more likely to
     be incidental/contextual than the article's actual subject).
  4. If still nothing, return region=None (article is likely national/
     international news with no specific region).

Matching is done with word-boundary-aware regex over every known
surface form, longest-match-first so "Bizerte-Sud" matches before the
shorter "Bizerte" governorate name would otherwise grab it.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from analysis.gazetteer import GOVERNORATES, DELEGATION_TO_GOVERNORATE
from analysis.text_utils import strip_diacritics as _strip_diacritics


def _is_arabic(text: str) -> bool:
    return any("\u0600" <= c <= "\u06FF" for c in text)


# Single-letter (and common two-letter combo) proclitics that attach
# directly to the following word with no space in Arabic: "and" (و),
# "so/then" (ف), "with/in/by" (ب), "like" (ك), "for/to" (ل), and simple
# combinations of these (e.g. "وب" = "and with"). Since every governorate
# gazetteer entry here already includes its own definite article (e.g.
# "القيروان" = "Al-Kairouan"), a plain word-boundary regex fails on
# "بالقيروان" ("in Kairouan") because "ب" sits immediately before it
# with no space -- there is no true word boundary there. We handle this
# by registering prefixed variants of every Arabic term instead of
# trying to get regex lookbehind to do it, which keeps the matching
# logic itself simple and uniform for Arabic and Latin script alike.
_ARABIC_PROCLITICS = ["ب", "ل", "ك", "ف", "و", "وب", "ول", "وك", "وف"]


def _with_arabic_prefix_variants(term: str) -> list[str]:
    if not _is_arabic(term):
        return [term]
    return [term] + [p + term for p in _ARABIC_PROCLITICS]


def _build_lookup() -> dict[str, str]:
    """
    Flatten gazetteer + delegations into {normalized_variant: canonical_governorate}.
    Delegations take priority at lookup time (checked first) since
    they're more specific than a bare governorate name.
    """
    lookup: dict[str, str] = {}
    for governorate, variants in GOVERNORATES.items():
        for v in variants:
            for variant_form in _with_arabic_prefix_variants(v):
                lookup[_strip_diacritics(variant_form.lower())] = governorate
    return lookup


def _build_delegation_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for delegation, governorate in DELEGATION_TO_GOVERNORATE.items():
        for variant_form in _with_arabic_prefix_variants(delegation):
            lookup[_strip_diacritics(variant_form.lower())] = governorate
    return lookup


_GOVERNORATE_LOOKUP = _build_lookup()
_DELEGATION_LOOKUP = _build_delegation_lookup()

# Sort all surface forms longest-first so multi-word names ("Le Kef",
# "Bizerte-Sud") are tried before shorter ones that might be substrings.
_ALL_DELEGATION_TERMS = sorted(_DELEGATION_LOOKUP.keys(), key=len, reverse=True)
_ALL_GOVERNORATE_TERMS = sorted(_GOVERNORATE_LOOKUP.keys(), key=len, reverse=True)


def _find_matches(text: str, terms: list[str]) -> list[str]:
    """Return every term (from `terms`) that appears in `text` as a
    whole word/phrase, using word boundaries adapted for both Latin and
    Arabic scripts (Arabic has no case, and \\b works reasonably with
    Arabic text in Python's re since Arabic letters are \\w)."""
    normalized = _strip_diacritics(text.lower())
    found = []
    for term in terms:
        if not term.strip():
            continue
        pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
        if re.search(pattern, normalized):
            found.append(term)
    return found


@dataclass
class RegionResult:
    region: Optional[str] = None
    confidence: float = 0.0
    method: str = "none"          # "gazetteer_title" | "gazetteer_body" | "none"
    matches: list[str] = field(default_factory=list)


def detect_region(title: str, body: str = "") -> RegionResult:
    # 1 & 2: title first, delegations before bare governorate names
    title_delegation_matches = _find_matches(title or "", _ALL_DELEGATION_TERMS)
    if title_delegation_matches:
        governorates = {_DELEGATION_LOOKUP[m] for m in title_delegation_matches}
        # If the title mentions delegations from a single governorate,
        # that's a confident, unambiguous hit.
        if len(governorates) == 1:
            return RegionResult(
                region=governorates.pop(),
                confidence=0.95,
                method="gazetteer_title",
                matches=title_delegation_matches,
            )
        # Multiple different governorates named in the title (e.g. a
        # cross-region story) -> return the first but flag lower
        # confidence and list all matches for the caller to inspect.
        return RegionResult(
            region=sorted(governorates)[0],
            confidence=0.5,
            method="gazetteer_title_multi",
            matches=title_delegation_matches,
        )

    title_gov_matches = _find_matches(title or "", _ALL_GOVERNORATE_TERMS)
    if title_gov_matches:
        governorate = _GOVERNORATE_LOOKUP[title_gov_matches[0]]
        return RegionResult(
            region=governorate,
            confidence=0.9,
            method="gazetteer_title",
            matches=title_gov_matches,
        )

    # 3: fall back to body, lower confidence
    if body:
        body_delegation_matches = _find_matches(body, _ALL_DELEGATION_TERMS)
        if body_delegation_matches:
            governorates = {_DELEGATION_LOOKUP[m] for m in body_delegation_matches}
            return RegionResult(
                region=sorted(governorates)[0],
                confidence=0.6 if len(governorates) == 1 else 0.35,
                method="gazetteer_body",
                matches=body_delegation_matches,
            )

        body_gov_matches = _find_matches(body, _ALL_GOVERNORATE_TERMS)
        if body_gov_matches:
            governorate = _GOVERNORATE_LOOKUP[body_gov_matches[0]]
            return RegionResult(
                region=governorate,
                confidence=0.5,
                method="gazetteer_body",
                matches=body_gov_matches,
            )

    # 4: nothing found -- likely national/international news
    return RegionResult()
