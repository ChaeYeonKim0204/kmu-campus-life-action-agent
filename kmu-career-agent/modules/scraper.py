"""modules/scraper.py — 안전한 학사 공지 수집 + 인메모리 파싱 [뼈대].

설계 의도(스펙 3.1):
- 봇 차단 회피: 표준 브라우저 User-Agent 주입 + 요청 간 1.5~3.0초 무작위 지연.
- 휘발성 처리: HTML 원본을 디스크에 저장하지 않고 RAM에서 즉시 제목/날짜/본문만
  추출한 뒤 파기.
- 네트워크 실패/미설정 시: 데모가 끊기지 않도록 인메모리 샘플 공지로 폴백.

⚠️ 현재는 뼈대 — fetch_notices()는 SAMPLE_NOTICES(플레이스홀더)를 돌려준다.
   실제 수집 로직은 아래 TODO + vibe-coding 프롬프트 참고해 채울 것.
"""
from __future__ import annotations

import random  # noqa: F401  (TODO에서 사용)
import time  # noqa: F401

from . import log_step

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# 데모용 가상 타겟. 실제 학교 서버를 두드리지 않도록 기본은 빈 리스트.
DEFAULT_NOTICE_URLS: list[str] = []

# 네트워크가 안 될 때(또는 뼈대 단계) 쓰는 인메모리 샘플 공지. 디스크 저장 X.
SAMPLE_NOTICES: list[dict] = [
    {
        "title": "[경영대학] 2026 AI 데이터톤 공모전 참가자 모집",
        "date": "2026-06-01",
        "body": (
            "AI빅데이터융합경영학과 재학생 대상 데이터톤. 주제: 캠퍼스 생활 데이터 기반 "
            "생성형 AI 서비스. 팀당 2~4인. 평가: 기술 구현 40 / 기획 30 / 발표 30."
        ),
        "source": "https://cba.kookmin.ac.kr/(가상)",
        "attachment_url": "https://cba.kookmin.ac.kr/notice/ai-datathon-2026.pdf",
    },
    {
        "title": "[대학본부] 교내 사회혁신 아이디어 경진대회",
        "date": "2026-05-28",
        "body": "사회문제 해결형 서비스 기획 공모. 코딩 비중 낮음, 기획·UX 중심.",
        "source": "https://www.kookmin.ac.kr/(가상)",
        "attachment_url": "",
    },
]


def fetch_notices(urls: list[str] | None = None, timeout: int = 8) -> list[dict]:
    """공지 목록을 수집해 [{title, date, body, source, attachment_url}, ...] 로 반환.

    뼈대: 지금은 SAMPLE_NOTICES를 반환한다.
    """
    urls = urls if urls is not None else DEFAULT_NOTICE_URLS
    log_step("scraper", f"공지 수집 시작 (타겟 {len(urls)}건)", status="run")

    # TODO(vibe-coding Prompt 2 / scraper):
    #   - requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    #   - 각 요청 전 time.sleep(random.uniform(1.5, 3.0)) 로 차단 회피
    #   - resp.text -> BeautifulSoup 파싱 -> 제목/날짜/본문만 추출
    #   - 추출 후 html 변수 즉시 파기(del) — 디스크 저장 절대 금지(인메모리만)
    #   - 실패 시 SAMPLE_NOTICES 로 폴백
    #
    # 예시 골격:
    #   notices = []
    #   for url in urls:
    #       time.sleep(random.uniform(1.5, 3.0))
    #       resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    #       soup = BeautifulSoup(resp.text, "html.parser")
    #       notices.append({"title": ..., "date": ..., "body": ..., ...})
    #       del resp, soup  # RAM에서 즉시 파기
    #   log_step("scraper", "RAM에서 HTML 즉시 파기 완료", status="ok")

    if not urls:
        log_step("scraper", "타겟 URL 미설정 → 인메모리 샘플 공지 사용(폴백)", status="warn")
        notices = [dict(n) for n in SAMPLE_NOTICES]
    else:
        raise NotImplementedError("실제 수집 로직 미구현 — 위 TODO 참고")

    log_step("scraper", f"공지 {len(notices)}건 수집 완료 (HTML 비저장)", status="ok",
             count=len(notices))
    return notices
