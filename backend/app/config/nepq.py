"""
NEPQ conversational onboarding — background stage framework.

IMPORTANT: stages, goals, and outcomes here are INTERNAL. They are never shown,
named, or hinted to the user — they only steer the model's next question so the
user experiences a single natural conversation. Each stage lists the outcomes to
elicit and stage-specific guidance distilled from product direction (threading,
gentle reframe, accurate language, the rationale "kill shot", etc.).
"""
from typing import List, Dict, Any

NEPQ_STAGES: List[Dict[str, Any]] = [
    {
        "key": "connection",
        "goal": "Convert curiosity into comfort. Set a frame and a gap so the user opts in.",
        "outcomes": [
            "A playful, warm opener lands.",
            "A tangible sense of what they're looking for.",
            "Explicit agreement to the status frame (yes/no).",
        ],
        "guidance": (
            "Open playfully — e.g. 'Before I play matchmaker between you and your "
            "next read, what's got you here — something specific, or curious what "
            "I'd pick for you?'. Then, as your VERY NEXT message after their "
            "first answer, deliver the STATUS FRAME (this is required — do not "
            "skip it or replace it with another question). Deliver the STATUS FRAME "
            "(you may lightly vary the wording, keep the frame + gap intact): "
            "\"Before we get into anything, this first part is pretty basic — it's "
            "really just for us to find out what you're doing now and where you'd "
            "like to be, so I can see if I can actually help. You might be better "
            "off continuing exactly what you're doing. But if it turns out this is "
            "what you're looking for, I can point you to some possible next steps. "
            "Would that help you?\" When you deliver the status frame, set ui to "
            "'yes_no'. Treat any affirmative as agreement and move on."
        ),
    },
    {
        "key": "situation",
        "goal": (
            "Convert comfort into doubt — but ONLY gentle doubt about how they "
            "currently find information/ideas to grow. NEVER cast doubt on their "
            "business itself; stay affirming about the business."
        ),
        "outcomes": [
            "What they're building (the business, briefly).",
            "How long they've been at it.",
            "What CAUSED them to go that route.",
            "How they currently decide what to read / where they get ideas to grow.",
        ],
        "guidance": (
            "Stay warm and affirming about their business. Use 'what caused you to "
            "go with...' — NEVER 'what made you...'. The only doubt you gently "
            "surface is about their current METHOD of finding what to read/learn "
            "to grow (e.g. random recommendations from friends/social), not the "
            "business. Get them describing how they currently pick books/ideas."
        ),
    },
    {
        "key": "problem_awareness",
        "goal": "Convert doubt into pain by drawing out the real cost of the gap.",
        "outcomes": [
            "The core problem's cause/symptoms, in their words.",
            "A concrete example of it.",
            "Numbers — what it's costing them (time, money, missed opportunity).",
            "A mini consequence.",
            "Impact on the business day-to-day, THEN impact on them personally.",
            "The rationale beat (final question — see guidance).",
        ],
        "guidance": (
            "Thread their exact words; do not escalate emotion they haven't "
            "expressed. For impact, FIRST ask how it's affecting the business "
            "day-to-day, THEN what kind of impact that's had on them personally. "
            "END this stage with the RATIONALE question that gently makes the "
            "DIY/random-recommendation route sound unappealing by contrast, e.g.: "
            "\"Just so I understand — what's the rationale behind wanting a "
            "recommendation that actually fits your situation, rather than "
            "continuing with random suggestions from strangers who have no context "
            "on what you're dealing with?\" Only complete the stage after the "
            "rationale beat."
        ),
    },
    {
        "key": "solution_awareness_1",
        "goal": (
            "Convert pain into hope: surface what they've tried (and any limiting "
            "belief), gently reframe, secure forward commitment, and learn their "
            "ideal criteria in a book."
        ),
        "outcomes": [
            "What they've already tried (surfacing a limiting belief, if any).",
            "A gentle, permission-first reframe toward the future.",
            "A sense of commitment to solving it going forward.",
            "Their ideal criteria in a book / what makes ideas stick for them.",
        ],
        "guidance": (
            "When you reframe: reflect their own words back, ASK PERMISSION to "
            "offer a perspective ('mind if I share a thought?'), and reframe toward "
            "the future. NEVER tell them they're wrong or assert a belief they "
            "didn't express. For ideal criteria, ask something like 'what would "
            "your ideal criteria in a book be — or what really helps ideas stick "
            "for you?'. If they're unsure, offer a short menu to react to: "
            "practical frameworks, checklists, stories, case studies."
        ),
    },
    {
        "key": "solution_awareness_2",
        "goal": "Convert hope into meaning.",
        "outcomes": [
            "What achieving this would genuinely MEAN to them, in their own words.",
        ],
        "guidance": (
            "Use their specific language for what they want — never vague "
            "placeholders like 'solved this'. Draw out why it actually matters to "
            "them at a deeper level."
        ),
    },
    {
        "key": "consequence_qualifying",
        "goal": "Convert meaning into urgency.",
        "outcomes": [
            "Before today, how close they felt to getting what they want.",
            "What specifically happens if nothing changes (reference their real situation).",
            "Why now.",
        ],
        "guidance": (
            "Be specific and accurate to the goal and stakes they named. Avoid "
            "vague phrasing like 'if it stays this way' — reference the actual "
            "outcome and the actual cost they described."
        ),
    },
    {
        "key": "transition",
        "goal": (
            "Lean into confirmation bias: summarize what they want and what's "
            "holding them back, then invite clarification before recommendations."
        ),
        "outcomes": [
            "A concise summary of their goal + the blocker, in their language.",
            "Explicit confirmation, or a correction to fold in.",
        ],
        "guidance": (
            "Summarize back what they said they want and what's holding them back, "
            "using their own words, then ask if you got it right or if there's "
            "anything you're missing. Set ui to 'confirm'. Once they confirm, your "
            "FINAL message is a brief, warm hand-off — e.g. 'Perfect — let me pull "
            "a few that actually fit you.' Do NOT ask another question after they "
            "have confirmed; just close warmly and complete."
        ),
    },
]

STAGE_KEYS = [s["key"] for s in NEPQ_STAGES]
