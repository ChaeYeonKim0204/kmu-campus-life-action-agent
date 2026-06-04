"""Small action state machine for follow-up document drafting flows."""

from __future__ import annotations

from tools.document_drafter import draft_action_document, missing_slots, slot_questions, supported_actions


SUPPORTED_ACTIONS = supported_actions()


def start_action(action_id: str) -> dict:
    """Start an action and return required questions."""
    if action_id not in SUPPORTED_ACTIONS:
        return {"status": "unsupported", "message": "아직 지원하지 않는 action입니다."}
    missing = missing_slots(action_id, {})
    return {
        "status": "needs_input",
        "action_id": action_id,
        "label": SUPPORTED_ACTIONS[action_id]["label"],
        "issue_type": SUPPORTED_ACTIONS[action_id]["issue_type"],
        "missing_slots": missing,
        "questions": slot_questions(action_id, missing),
        "privacy_notice": "학번, 실명, 주민번호, 연락처, 포털 ID/PW 등 개인정보는 입력하지 마세요.",
    }


def continue_action(action_id: str, slots: dict, policy_chunks: list[dict] | None = None) -> dict:
    """Continue an action with user slot values."""
    if action_id not in SUPPORTED_ACTIONS:
        return {"status": "unsupported", "message": "아직 지원하지 않는 action입니다."}
    missing = missing_slots(action_id, slots)
    if missing:
        return {
            "status": "needs_input",
            "action_id": action_id,
            "label": SUPPORTED_ACTIONS[action_id]["label"],
            "issue_type": SUPPORTED_ACTIONS[action_id]["issue_type"],
            "missing_slots": missing,
            "questions": slot_questions(action_id, missing),
            "privacy_notice": "학번, 실명, 주민번호, 연락처, 포털 ID/PW 등 개인정보는 입력하지 마세요.",
        }
    draft = draft_action_document(action_id, slots, policy_chunks or [])
    return {"status": "completed", "action_id": action_id, **draft}
