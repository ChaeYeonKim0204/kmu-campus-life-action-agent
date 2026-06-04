# 작업계획: '전공선택 신뢰' 롤백 + HITL 이수구분 편집

> 배경(사용자 결정 2026-06-04): 전과 등으로 성적표 이수구분 자체를 신뢰할 수 없는 케이스가 있다
> → 자동 신뢰(d229bfb의 강등 제거) 대신 **원래 보수적 강등으로 롤백**하고, 대신 **검증 테이블(HITL)에서
> 사용자가 이수구분을 직접 수정**할 수 있게 한다. HITL 설계 철학(자동 판정 대신 사람 확정)과 일관.

## 롤백 vs 유지 분리 (d229bfb·d23f3da 중)

| 항목 | 처분 | 근거 |
|---|---|---|
| verification.py 강등 제거(신뢰) | **롤백** — `aggregate_only & area==전공 → 일반선택` 복원 | 전과 케이스에서 오신뢰. 강등돼도 사용자가 편집으로 복구 가능(신규 기능) |
| `_ISU_TO_AREA` 코드표 매핑(다전공·제2전공·연계융합(전공) 등) | **유지** | 신뢰와 무관한 substring 섀도잉 잠복 결함 수정 — 롤백하면 다전공 이수구분이 다시 전공 오산입 |
| audit_v2 overlap `or area=="전공"` + fusion id-dedup | **유지** | 이제 **사용자 편집 경로의 가드** — 카탈로그 밖 과목을 사용자가 전공으로 바꾸면 동일한 융합 무캡 이중인정 위험. 강등 복원 시 자동 경로로는 도달 불가, 편집 경로로 도달 |
| overlap_courses[].assignment 노출·게이지 연동·학기 정렬 | **유지** | 독립 기능 |

## 신규: 검증 테이블 이수구분 편집

- **Backend 변경 0**: verification_table은 이미 클라이언트→`/audit` round-trip이고 `finalize_transcript`가
  행의 `requirement_area`를 그대로 집계. 잘못된 값은 `VerifiedCourse`의 `Area` Literal이 ValidationError→400.
- **Frontend** (`GraduationV2.jsx` 검증 테이블):
  - **aggregate_only 행만** 이수구분 셀을 `<select>`(전공/기초교양/핵심교양/자유교양/일반선택)로.
    카탈로그 매칭 행은 요람 근거가 있으므로 편집 불가(툴팁 "요람 교과과정표 기준") — 전과생의 타과 과목은
    어차피 카탈로그 밖이라 편집 가능 집합에 들어옴.
  - 변경 시 기존 `tableDirty`(JSON 비교)가 자동 발동 → 상담 입력 비활성 + "재사정 먼저" 가드 그대로 동작.
  - 캐비엣 1줄: "핵심교양으로 변경 시 세부영역(인문Ⅰ 등)은 미배정 — 총량에만 산입".
  - 강등된 행(이수구분 원문이 전공계인데 일반선택로 잡힌)을 사용자가 알 수 있게 비고에 표시:
    `exclude_reason`과 별개로 표시 전용 — `aggregate_only && 일반선택`이면 select 옆에 점(•) 강조는 과함,
    placeholder는 현행 유지(편집 가능 자체가 안내). 문서로만 안내.
- **core_area**: 사용자가 핵심교양으로 변경한 행은 `core_area=None` 유지(세부영역 산입 없음 — 정직).

## 테스트

1. 강등 복원: 카탈로그 밖 "전공선택" → 일반선택 + aggregate_only (기존 `test_trusted_major_isugubun_not_demoted` 를 반대로 수정·개명).
2. 편집 경로: 테이블 행 `requirement_area`를 전공으로 바꿔 `/audit` → 전공 집계 + (융합 prefix면) overlap 가드 동작 — 기존 `test_trusted_major_with_conv_prefix_no_double_count`가 VerifiedCourse 직접 구성이라 **편집 경로와 동형** → docstring만 갱신해 유지.
3. 코드표 매핑·학기 정렬 테스트 불변.
4. API: 잘못된 area 문자열 → 400.

## 문서·실행

- `trust_isugubun_plan.md` 머리에 롤백 결정 기록(추적성), current_state §1 HITL 행에 "이수구분 편집" 추가.
- 검증: pytest 전체 + 빌드 + 실행 라운드(데모 4명 수치 불변 — 데모 xls는 강등 대상 0건이라 양방향 무영향 기실측 + 편집 시나리오 1건 API 재현).
