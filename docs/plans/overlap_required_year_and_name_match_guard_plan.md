# 작업계획: 융합 전공필수 학번 요람 기준 + 이름매칭 prefix 가드 + CE 구명칭

> 사용자 실파일 검증 발견 3건 (2026-06-04).

## ① 융합 블록 '전공필수' 배지 = 학생 학번 요람 기준

- 현재: `audit_v2._convergence_checks`의 `required_prefixes`가 **다른 프로그램 카탈로그(2025 단일본)의
  `is_required`**로 산출 → 중복인정 우선순위·"전공필수는 융합 이동 불가" 가드·배지가 2025 기준 고정.
  예: 유레카는 2025만 필수인데 2022학번에게도 필수 배지.
- 수정: 헬퍼 `_required_prefixes_for_year(ppid, year)` — `_required_names_for_year(ppid, year)`(이미
  nearest-prior)를 그 프로그램 카탈로그 `by_norm`으로 코드 해석 → 앞5자리 집합. choose-1 그룹 멤버는
  '택1'이라 필수 고정 대상에서 제외(중복인정 우선엔 단일 필수만). **연도 데이터 없는 프로그램은 기존
  `is_required` 폴백.** `_convergence_checks`에 admission year 전달(시그니처 확인 후 — compute_audit이 보유).

## ② 이름매칭(match_course ②단계)에 앞5자리 가드

- 현재: 코드 미스 시 이름 유니크 매칭 — **타과 동명 과목**(사제동행세미나·S-TEAM 등 전교 공통 과목,
  학과별 코드)이 본전공 과목으로 오매칭.
- 수정: raw에 코드가 있고 `normalize_code(raw)[:5] != 매칭 후보 course_id[:5]`면 이름매칭 거부 →
  ③ aggregate로(이수구분 기반 + 강등/HITL 편집). 동일교과목 코드 개편은 앞5자리 유지 규칙이라 구과정
  코드도 안전. 코드가 아예 없는 행(요람 조인용)은 기존대로 이름매칭 허용.
- **알려진 잔여 구멍(이번 범위 밖, 정직 고지)**: 필수과목 '판정'(`_taken`)은 이름 기반이라 타과
  사제동행도 이름으로 택1을 충족시킴 — 분류는 이번에 고치고, 판정의 prefix 검증은 별도 결정 필요
  (판정까지 코드 기반으로 좁히면 구과정 필수가 HITL 편집 전까지 미이수로 뜨는 트레이드오프).

## ③ College English 구명칭 매칭

- 현재: gen_basic any_of ["College EnglishⅠ","College EnglishⅡ"] — 정규화가 Ⅰ/1/I는 흡수하지만
  **무번호 "College English"**(구명칭/타요람 표기)는 부분일치(`key in t`) 실패.
- 수정(데이터): any_of에 "College English" 추가(라벨은 "College EnglishⅠ·Ⅱ 중 택1" 유지) — 구명칭
  이수도 충족 처리. 코드 변경 0.

## 검증

테스트: ①연도별 required_prefixes(2022학번 유레카 비필수 vs 2025학번 필수) ②타과 코드 사제동행
이름매칭 거부→aggregate ③CE 무번호 충족. 전체 pytest + 데모 4명 실행 라운드(불변 기대 — 데모는
정확 코드·CE Ⅰ 이수) + 빌드.
