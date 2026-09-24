"""Shared, inspectable challenge vocabulary for ranking and fit explanations.

Match bounded phrases in the reader's words and existing catalog metadata. No
provider, title allowlist, inferred purchase, or change to the saved profile.
These are topic signals, not semantic understanding or guarantees of book fit.
"""
import re
from html import unescape
from typing import Any

from app.services import founder_knowledge as fk


CONCEPTS = {
    "client_acquisition": (
        "customer acquisition and lead flow",
        r"client acquisition|customer acquisition|lead (?:flow|generation|gen)|leads|"
        r"referrals?|word of mouth|local marketing|pipeline|"
        r"(?:find|get|attract|acquire|more|new|enough) (?:\w+ ){0,2}(?:clients?|customers?)|"
        r"client volume|customer volume|reinvest in acquisition",
    ),
    "pricing": (
        "pricing and margins",
        r"pricing|price|prices|undercharg\w*|overcharg\w*|margins?|"
        r"scope creep|scope definition|flat fee|charge for value|value based|"
        r"value pricing|hourly rate|billable hour|profitability",
    ),
    "cash_flow": (
        "cash flow and owner pay",
        r"cash(?: flow)?|runway|owner pay|pay myself|"
        r"money in (?:the |my |our )?(?:bank|account)|envelope system|"
        r"where (?:it|the money) (?:all )?goes",
    ),
    "owner_dependence": (
        "owner dependence and delegation",
        r"owner (?:dependence|dependency|replacement)|delegat\w*|"
        r"depends (?:entirely )?on me|every decision|nothing is documented|"
        r"without (?:me|you)|beyond yourself|working on vs in|"
        r"(?:run|runs) itself|step back|hire (?:someone|a manager)|"
        r"(?:business|everything) (?:stops|falling apart)|"
        r"(?:i am|i'm|you are|you're) (?:the |a )?bottleneck",
    ),
    "validation": (
        "testing demand before building",
        r"validat\w*|customer discovery|customer interviews?|"
        r"product market fit|problem solution fit|"
        r"(?:nobody|anyone) (?:actually )?(?:wants|needs)|worth building|"
        r"test\w* (?:a |an |the |your )?(?:idea|assumption|demand)",
    ),
    "customer_retention": (
        "customer retention and activation",
        r"churn|customer retention|customer success|activation|"
        r"onboarding|lifelong loyalty|(?:users?|customers?) (?:leave|leaving)|"
        r"sign up and (?:then )?(?:vanish|leave)|never come back",
    ),
    "team_leadership": (
        "leading and retaining a team",
        r"leadership|managing managers|manag\w* (?:a |the |my |our )?team|"
        r"team building|people management|employee retention|staff retention|"
        r"(?:employee|staff|cleaner)s? (?:turnover|leave|leaving)|"
        r"leading a growing team|managing people|leadership layer",
    ),
    "focus": (
        "focus and sustainable work",
        r"burn(?:ed|t)? out|burnout|overwhelm\w*|prioriti\w*|"
        r"productivity|focus|time management|work less|"
        r"(?:seventy|70) hour|half finished",
    ),
    "positioning": (
        "positioning and differentiation",
        r"positioning|differentiat\w*|undifferentiated|"
        r"look identical|obvious choice|competitors?|niche|niching",
    ),
    "delivery": (
        "delivery capacity and repeatable operations",
        r"fulfil\w*|delivery|service delivery|quality|"
        r"documentation|documented processes|workflow|process improvement|"
        r"constraints?|throughput|orders come in",
    ),
    "sales_process": (
        "a repeatable sales process",
        r"sales (?:process|motion|pipeline|conversion)|"
        r"repeatable sales|sales rep|hiring a rep|closes?|deals?|prospecting",
    ),
    "self_belief": (
        "confidence and taking action",
        r"self belief|self doubt|self confidence|procrastinat\w*|"
        r"second guess\w*|not good enough|imposter|mindset|"
        r"success habits|confidence",
    ),
    "channels": (
        "finding effective acquisition channels",
        r"channels?|paid ads|advertising|facebook|tiktok|influencers?|"
        r"growth hacking|viral\w*",
    ),
    "network_effects": (
        "marketplace network effects",
        r"network effects?|chicken and egg|critical mass|two sided|"
        r"buyers without sellers|sellers without buyers",
    ),
}
PATTERNS = {
    key: re.compile(r"\b(?:" + expression + r")\b")
    for key, (_, expression) in CONCEPTS.items()
}
STEMS = {
    "procrastinat", "motivat", "overwhelm", "priorit", "differentiat",
    "acqui", "operation", "deliver", "scal", "efficien", "fulfil",
    "financ", "fundrais", "delegat",
}


def normalize(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    text = unescape(re.sub(r"<[^>]*>", " ", text)).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[_\-–—]", " ", text)).strip()


def concepts(text: Any) -> set[str]:
    text = normalize(text)
    return {key for key, pattern in PATTERNS.items() if pattern.search(text)}


def domains(text: Any) -> set[str]:
    text = normalize(text)
    return {
        domain for domain, keywords in fk.CHALLENGE_KEYWORDS.items()
        if any(re.search(r"\b" + re.escape(word) +
                         (r"\w*" if word in STEMS else r"(?:s|es)?") + r"\b", text)
               for word in keywords)
    }


def book_text(book: Any) -> str:
    # Specific catalog content differentiates books with the same broad tags.
    fields = [getattr(book, name, None) for name in ("promise", "best_for", "description")]
    for name in ("functional_tags", "theme_tags", "core_frameworks", "outcomes"):
        fields.extend(getattr(book, name, None) or [])
    return " ".join(value for value in fields if isinstance(value, str))


def book_concepts(book: Any) -> set[str]:
    return concepts(book_text(book))


def text_match(reader_text: Any, catalog_text: Any) -> float:
    """Match prose through the same vocabulary rather than sentence containment."""
    wanted, covered = concepts(reader_text), concepts(catalog_text)
    if wanted:
        return len(wanted & covered) / len(wanted)
    return float(bool(domains(reader_text) & domains(catalog_text)))


def priority_concepts(ctx: dict) -> set[str]:
    # A future aspiration or selected area must not impersonate today's problem.
    challenge = normalize(ctx.get("biggest_challenge"))
    return concepts(challenge or ctx.get("vision"))


def matched_concepts(ctx: dict, book: Any) -> list[str]:
    return sorted(priority_concepts(ctx) & book_concepts(book))


def specific_score(ctx: dict, book: Any) -> float:
    matches = matched_concepts(ctx, book)
    # Bounded: repeating words/tags cannot inflate the signal. The first concrete
    # connection matters most; multiple relevant connections get a smaller boost.
    return 6.0 + min(2.0, len(matches) - 1) if matches else 0.0
