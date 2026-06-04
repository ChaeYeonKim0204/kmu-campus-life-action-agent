"""Public tool facade for the KMU Campus Life Action Agent."""

from agent.answer_builder import build_final_answer
from agent.classifier import classify_issue as classify_academic_issue
from retriever.hybrid_retriever import HybridRetriever
from tools.checklist import generate_checklist
from tools.contact_router import route_contact
from tools.deadline import calculate_deadline
from tools.document_drafter import draft_action_document


def search_official_policy(issue_type: str, query: str) -> list[dict]:
    """Search local official policy chunks with hybrid retrieval."""
    return HybridRetriever().search(query, issue_type=issue_type)


__all__ = [
    "classify_academic_issue",
    "search_official_policy",
    "calculate_deadline",
    "generate_checklist",
    "route_contact",
    "draft_action_document",
    "build_final_answer",
]
