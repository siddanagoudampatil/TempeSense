"""Deterministic checks that run on the raw question, before any LLM call.

classify_request   -> "refused" | "out_of_scope" | None
has_time_cue       -> does the question contain any time wording at all?
masked_blocks      -> already-masked house numbers the user typed (e.g. "7XX")

These are intentionally conservative regexes. A miss falls through to the normal agent path;
a false positive would wrongly block a real question, so each pattern needs a specific phrase.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

MASKED_BLOCK = re.compile(r"\b(\d{1,4})\s?([xX]{1,3})\b")

_UNMASK_VERB = re.compile(
    r"\b(un-?mask\w*|de-?mask\w*|de-?obfuscat\w*|un-?obfuscat\w*|reveal\w*|uncensor\w*)\b", re.IGNORECASE
)
_EXACT_ADDRESS = re.compile(
    r"\b(exact|real|actual|full|precise|true|complete)\s+(house\s+|street\s+|building\s+)?"
    r"(number|address|location|coordinates)\b",
    re.IGNORECASE,
)
_COORDINATES = re.compile(r"\b(latitude|longitude|gps|coordinates|lat\s?/?\s?long)\b", re.IGNORECASE)
_OFFENSE_WORDS = re.compile(
    r"\b(incident|incidents|offense|offenses|crime|crimes|police|report|reports|reported|theft|thefts|"
    r"burglary|assault|robbery|victim|victims)\b",
    re.IGNORECASE,
)

_ROAD_WORDS = re.compile(
    r"\b(closure|closures|closed|close|construction|restriction|restrictions|barricade|barricades|lane|lanes|"
    r"road|roads|street|streets|ave|avenue|blvd|rd|dr|detour|traffic)\b",
    re.IGNORECASE,
)

# Domains the city publishes but this agent has no tool for yet. Remove an entry when its tool is built.
UNSUPPORTED_DOMAINS: List[Tuple[str, re.Pattern]] = [
    ("solid waste and recycling", re.compile(
        r"\b(recycl\w*|bulk\s+(trash|pickup|pick-up|item\w*)|solid\s+waste|garbage\s+(pick\s?-?up|collection|day)|"
        r"trash\s+(pick\s?-?up|collection|day)|green\s+waste|(blue|green|black)\s+(bin|barrel))\b", re.IGNORECASE)),
    ("code compliance", re.compile(
        r"\b(code\s+(compliance|enforcement)|overgrown|weeds?|property\s+maintenance|nuisance\s+complaints?)\b",
        re.IGNORECASE)),
    ("weather", re.compile(r"\b(weather|forecast|temperatures?|rain(ing|fall)?|humidity|monsoon)\b", re.IGNORECASE)),
]

REFUSAL_MESSAGE = (
    "I can't provide exact house numbers or coordinates for police incidents. The City masks them "
    "(for example 7XX E APACHE BLVD) to protect privacy, and I don't try to reverse that. "
    "I can still search by the masked block, street, or area."
)


def masked_blocks(text: str) -> List[str]:
    """Masked house numbers typed in the question, upper-cased (e.g. ['7XX'])."""
    return [f"{num}{x}".upper() for num, x in MASKED_BLOCK.findall(text or "")]


def classify_request(text: str) -> Optional[Tuple[str, str]]:
    """Return (status, message) when the request must not reach the query tools, else None."""
    text = text or ""
    offense_context = bool(_OFFENSE_WORDS.search(text))
    masked = bool(masked_blocks(text))

    if _UNMASK_VERB.search(text) and (masked or offense_context or "address" in text.lower()):
        return "refused", REFUSAL_MESSAGE
    if _EXACT_ADDRESS.search(text) and (masked or offense_context):
        return "refused", REFUSAL_MESSAGE
    if _COORDINATES.search(text) and offense_context:
        return "refused", REFUSAL_MESSAGE

    for domain, pattern in UNSUPPORTED_DOMAINS:
        # A weather word inside a road or crime question ("rain damage repairs") is not a weather question.
        if domain == "weather" and (offense_context or _ROAD_WORDS.search(text)):
            continue
        if pattern.search(text):
            return "out_of_scope", (
                f"I can only answer questions about police general offenses and street closures. "
                f"Questions about {domain} are outside what I can look up."
            )
    return None


_TIME_CUE = re.compile(
    r"\b(today|tonight|tomorrow|yesterday|now|currently|current|active|ongoing|recent|recently|latest|lately|"
    r"upcoming|soon|past|last|next|this|since|before|after|during|until|between|"
    r"week|weeks|weekend|weekends|month|months|year|years|day|days|hour|hours|"
    r"morning|afternoon|evening|night|midnight|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|spring|summer|fall|autumn|winter|q[1-4])\b"
    r"|\b(19|20)\d{2}\b|\b\d{1,2}/\d{1,2}(/\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)


def has_time_cue(text: str) -> bool:
    """True if the question contains any wording about time. Deliberately permissive: a false 'True'
    only keeps the model's date, which is today's behavior; a false 'False' would drop a real window."""
    return bool(_TIME_CUE.search(text or ""))


_RESTRICTION_CUE = re.compile(
    r"\b(closure|closures|closed|close|closing|shut|shutdown|roadway|minor|multiple)\b", re.IGNORECASE
)
_RESTRICTION_COND = r"RestrictionType\s*(?:NOT\s+LIKE|LIKE|=|<>|!=)\s*'[^']*'"


def drop_unrequested_restriction_filter(question: str, where: str) -> Tuple[str, bool]:
    """Remove a RestrictionType condition the user never asked for.

    The model sometimes invents one from loose words ("work", "incident") or even writes
    NOT LIKE '%Closure%'. Only simple AND-joined conditions are removed; anything more complex is
    left untouched rather than risk producing broken SQL. Returns (where, dropped).
    """
    if not where or "restrictiontype" not in where.lower() or _RESTRICTION_CUE.search(question or ""):
        return where, False
    new = re.sub(rf"\s+AND\s+{_RESTRICTION_COND}", "", where, count=1, flags=re.IGNORECASE)
    if new == where:
        new = re.sub(rf"{_RESTRICTION_COND}\s+AND\s+", "", where, count=1, flags=re.IGNORECASE)
    if new == where:
        new = re.sub(rf"^\s*{_RESTRICTION_COND}\s*$", "1=1", where, count=1, flags=re.IGNORECASE)
    if new == where or "restrictiontype" in new.lower():
        return where, False
    return new.strip(), True


def split_multiword_like(where: str, field: str = "OffenseCustom") -> Tuple[str, bool]:
    """Make multi-word LIKE patterns on `field` independent of word order.

    The city's offense labels read 'THEFT OF BICYCLE', 'THEFT FROM BUILDING', 'MOTOR VEHICLE THEFT'; a model
    that writes LIKE '%BICYCLE THEFT%' can never match. Each phrase becomes a parenthesized AND of
    single-word patterns, so precedence with any surrounding OR is preserved.
    """
    changed = False

    def repl(match: "re.Match[str]") -> str:
        nonlocal changed
        words = match.group(1).split()
        if len(words) < 2:
            return match.group(0)
        changed = True
        return "(" + " AND ".join(f"{field} LIKE '%{w}%'" for w in words) + ")"

    new = re.sub(rf"{field}\s+LIKE\s+'%([^%']*)%'", repl, where or "", flags=re.IGNORECASE)
    return (new, True) if changed else (where, False)
