"""
CLI harness to play through the NEPQ onboarding conversation end-to-end.

Usage (from backend/, with ANTHROPIC_API_KEY in env):
    python -m app.scripts.nepq_repl

Type your replies as the user. The hidden stage is shown in [brackets] for the
operator only (it is NEVER sent to a real user). At the end it prints the
structured profile the scribe inferred.
"""
import json
import sys

from app.config.nepq import NEPQ_STAGES
from app.services.nepq_conversation import next_turn, extract_profile

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
RESET = "\033[0m"


def main() -> None:
    history = []
    stage_index = 0
    turns_in_stage = 0
    max_turns = 40

    # Opening bot turn
    turn = next_turn(history, stage_index, turns_in_stage)
    stage_index, turns_in_stage = turn["stage_index"], turn["turns_in_stage"]
    history.append({"role": "assistant", "content": turn["message"]})

    for _ in range(max_turns):
        ui = f"  {DIM}(ui: {turn['ui']}){RESET}" if turn.get("ui") else ""
        print(f"\n{CYAN}{BOLD}Readar{RESET} {DIM}[{turn['stage_key']}]{RESET}{ui}\n  {turn['message']}\n")

        if turn.get("done"):
            print(f"{GREEN}— conversation complete —{RESET}\n")
            break

        try:
            user_input = input(f"{BOLD}You{RESET}  ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n(exiting)")
            return
        if user_input.lower() in {"/quit", "/exit"}:
            return
        history.append({"role": "user", "content": user_input})

        turn = next_turn(history, stage_index, turns_in_stage)
        stage_index, turns_in_stage = turn["stage_index"], turn["turns_in_stage"]
        history.append({"role": "assistant", "content": turn["message"]})

    print(f"{DIM}Extracting structured profile (scribe)…{RESET}")
    profile = extract_profile(history)
    print(f"\n{GREEN}{BOLD}Scribe — inferred profile:{RESET}")
    print(json.dumps(profile, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
