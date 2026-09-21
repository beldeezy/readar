"""Grounded recommendation copy, derived from the same profile and catalog as scoring.

These are topic connections, not guarantees or an explanation of every ranking
weight. No model call, client-supplied book metadata, or inferred reader facts.
"""
import re
from html import unescape
from typing import Any, Dict, Optional

from app.services import founder_knowledge as fk


STAGE_LABELS = {
    "idea": "idea",
    "pre-revenue": "pre-revenue",
    "early-revenue": "early-revenue",
    "scaling": "scaling",
}
READING_FOCUS = {
    "mindset": "Look for one habit you could try this week, then notice what changes.",
    "strategy": "Look for one decision you could clarify before taking your next step.",
    "sales": "Look for one idea you could test in your next customer conversation.",
    "operations": "Look for one repeatable task you could simplify this week.",
    "finance": "Look for one financial assumption you could check against your own numbers.",
    "leadership": "Look for one idea you could try in your next team conversation.",
}
# Only known word stems accept arbitrary suffixes. In particular, "lead" must
# not turn "leadership" into a sales match, nor "self" match "shelf".
STEMS = {
    "procrastinat", "motivat", "overwhelm", "priorit", "differentiat",
    "acqui", "operation", "deliver", "scal", "efficien", "fulfil",
    "financ", "fundrais", "delegat",
}


def _text(value: Any, limit: int = 240) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = unescape(re.sub(r"<[^>]*>", " ", value))
    value = " ".join(value.split())
    if not value:
        return None
    if len(value) > limit:
        value = value[:limit - 1].rsplit(" ", 1)[0] + "…"
    return value


def _contains(text: str, keyword: str) -> bool:
    suffix = r"\w*" if keyword in STEMS else r"(?:s|es)?"
    return bool(re.search(r"\b" + re.escape(keyword) + suffix + r"\b", text))


def _reader_domains(text: Optional[str]) -> set:
    normalized = (text or "").lower().replace("_", " ")
    return {
        domain for domain, keywords in fk.CHALLENGE_KEYWORDS.items()
        if any(_contains(normalized, keyword) for keyword in keywords)
    }


def _book_domains(book: Any) -> set:
    domains = set()
    for tag in getattr(book, "functional_tags", None) or []:
        domain = fk.FUNCTIONAL_TO_DOMAIN.get(str(tag).strip().lower())
        if domain:
            domains.add(domain)
    for tag in getattr(book, "theme_tags", None) or []:
        normalized = str(tag).strip().lower().replace("_", " ")
        for keyword, domain in fk.THEME_KEYWORD_TO_DOMAIN.items():
            if _contains(normalized, keyword.replace("_", " ")):
                domains.add(domain)
    return domains


def _evidence(book: Any) -> Optional[str]:
    # Attribute the catalog text separately from our matching explanation.
    for field in ("promise", "best_for"):
        value = _text(getattr(book, field, None))
        if value:
            return value
    for outcome in getattr(book, "outcomes", None) or []:
        value = _text(outcome)
        if value:
            return value
    return _text(getattr(book, "description", None))


def build_book_fit(user_ctx: Optional[Dict[str, Any]], book: Any) -> Dict[str, Any]:
    ctx = user_ctx or {}
    challenge = _text(ctx.get("biggest_challenge"), 180)
    goal = _text(ctx.get("vision"), 180)
    domains = _book_domains(book)
    evidence = _evidence(book)
    result = {
        "priority": challenge or goal,
        "priority_label": "Your challenge" if challenge else "Your goal",
        "reason": "This is a broader suggestion. We haven't established a direct connection to your priority yet.",
        "evidence": evidence,
        "reading_focus": "Check the contents or a sample for an idea that speaks to your priority before choosing this book.",
        "match_type": "general",
    }
    for kind, priority in (("challenge", challenge), ("goal", goal)):
        overlap = domains & _reader_domains(priority)
        if overlap:
            # Stable domain order keeps explanations consistent across requests.
            domain = next(key for key in fk.DOMAIN_KEYS if key in overlap)
            label = fk.DOMAIN_LABELS[domain].lower().replace(" & ", " and ")
            result.update(
                priority=priority,
                priority_label="Your challenge" if kind == "challenge" else "Your goal",
                reason=f"Your {kind} touches on {label}, an area covered by this book's listed topics.",
                reading_focus=READING_FOCUS[domain],
                match_type=kind,
            )
            return result

    stage = ctx.get("business_stage")
    stages = getattr(book, "business_stage_tags", None) or []
    if stage in STAGE_LABELS and stage in stages:
        result.update(
            reason=f"This book is listed for founders at the {STAGE_LABELS[stage]} stage. That's a stage connection; we haven't established a specific match to your challenge yet.",
            match_type="stage",
        )
    elif not challenge and not goal:
        result["reason"] = "A general suggestion. Add your current challenge to help us explain a personal connection."
    elif not evidence and not domains:
        result["reason"] = "We don't have enough book details to explain a personal connection yet."
    return result


def fit_summary(fit: Dict[str, Any]) -> str:
    """Keep older paragraph consumers as accurate as the structured card."""
    priority = f'{fit["priority_label"]}: “{fit["priority"]}” ' if fit["priority"] else ""
    evidence = f' Book details: “{fit["evidence"]}”' if fit["evidence"] else ""
    return priority + fit["reason"] + evidence
