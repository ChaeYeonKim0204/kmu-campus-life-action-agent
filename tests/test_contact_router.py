from retriever.hybrid_retriever import HybridRetriever
from tools.contact_router import route_contact


def test_routes_certificate_to_service_center():
    chunks = HybridRetriever().search("졸업예정증명서 어디서 뽑아?", "certificate")
    contacts = route_contact("certificate", chunks)
    assert any("종합서비스센터" in contact["name"] for contact in contacts)


def test_routes_military_attendance():
    chunks = HybridRetriever().search("예비군 때문에 결석", "attendance")
    contacts = route_contact("attendance", chunks)
    assert any("교강사" in contact["name"] for contact in contacts)

