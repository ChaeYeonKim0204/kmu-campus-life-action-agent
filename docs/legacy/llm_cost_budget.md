# LLM 비용 예산 (모델 팀)

> 측정일: 2026-05-28 (Phase 1-8). 모델: `gpt-5-mini`, 임베딩: `text-embedding-3-small`.
> 가격 기준 (2026-01 OpenAI 공시):
> - `gpt-5-mini`: input $0.25 / 1M tokens · output $2 / 1M tokens · cached input $0.025 / 1M
> - `text-embedding-3-small`: $0.02 / 1M tokens

## 1. 1회 호출 평균 (실측 기반 추정)

| 노드 | 모델 | input tokens | output tokens | reasoning | 회당 비용 (USD) |
|---|---|---:|---:|---:|---:|
| `/ask` `expand_search_query` | gpt-5-mini | ~250 | ~350 | minimal (0) | $0.001 |
| `/ask` `rerank_chunks` | gpt-5-mini | ~700 | ~50 | minimal (0) | $0.0003 |
| `/ask` `polish_answer` | gpt-5-mini | ~1,000 | ~700 | minimal (0) | $0.0017 |
| `/ask` **합계** (3노드 다 ON) | | | | | **≈ $0.003** |
| `/graduation/audit` GPT 분석 | gpt-5-mini | ~2,000 | ~600 | minimal (0) | $0.0017 |
| `/graduation/*` RAG query embedding | text-embedding-3-small | ~30 | — | — | $0.000001 |
| 졸업센터 호출 **합계** | | | | | **≈ $0.002** |

**`reasoning_effort=minimal` 적용으로 reasoning_tokens=0** → 본 가격은 출력 토큰에만 부과되어 안정적. minimal 끄면 reasoning 100~250 토큰이 추가로 잡혀 비용·지연 모두 2~3배.

## 2. 일회성 인덱스 빌드

| 작업 | 모델 | 입력 토큰 | 비용 |
|---|---|---:|---:|
| 요람 PDF 1106페이지 → 1056 chunks 임베딩 | text-embedding-3-small | ~210K | **≈ $0.004** |

→ 재빌드 거의 안 함 (요람 개정 시에만).

## 3. 발표 데모 안전 마진

가정: 발표 당일 30회 시연, 사전 리허설 50회, 평소 개발 100회.

| 항목 | 추정 호출 수 | 비용 |
|---|---:|---:|
| `/ask` (보조 3노드 ON) 데모·리허설 | 100 | $0.30 |
| `/graduation/audit` | 30 | $0.06 |
| 인덱스 빌드 1회 | 1 | $0.004 |
| 개발 중 잡호출·실패 retry | 200 | $0.60 |
| **P5 졸업센터 8 task 풀 회귀** | 회당 8 호출 | $0.02 / 회 |
| **총 추정** | | **≈ $1.0** |

키 충전 ≈$10 기준 **마진 10배 이상**. 안전.

### 3.1 P5 풀 회귀 실측 (2026-05-28, Phase 5 commit 5)

- **8 task × 1회 호출 = 총 ~104초 (실시간), 평균 13초/task**
- 비용 추정 ≈ **$0.016** (task당 input 2K + output 600 토큰 가정, gpt-5-mini 단가 기준)
- 정확한 비용은 OpenAI 대시보드 → Usage 페이지에서 확인 (P1 usage 로그는 `llm_client.py` 경로만 기록하므로 graduation_center 호출은 별도 집계 필요 — Phase 6 후속 과제)
- 시연 직전 풀 회귀 1회면 충분; CI에서는 `@pytest.mark.live_llm`으로 기본 skip.

## 4. 비용 통제 가드 (Phase 0에서 이미 적용)

| 가드 | 효과 |
|---|---|
| `max_output_tokens`: expand=400, rerank=400, polish=1500 | 출력 폭주 차단 |
| `reasoning={"effort":"minimal"}` (gpt-5/o-series 자동 적용) | reasoning 토큰 0으로 → 비용·지연 50% 절감 |
| `_supports_temperature` 가드 | API 거부로 인한 무한 retry 방지 |
| `OPENAI_POLISH_ENABLED=false` 토글 | 데모 외 시간엔 polish 끄면 가장 비싼 노드 차단 |
| `agent.answer_validator` 거부 fallback | 깨진 polish 결과로 재호출 시도 안 함 |

## 5. 모니터링 (Phase 2-2 예정)

- `data/state/llm_usage.jsonl` 호출별 1줄 (timestamp / node / model / input_tokens / output_tokens / cost_estimate)
- 일자별 누적·노드별 분포 추적 가능
- 키 잔액은 OpenAI 대시보드에서 직접 확인 (Phase 4-1)

## 6. 관찰 메모

- gpt-5-mini의 `max_output_tokens`은 **reasoning 토큰을 포함**한다는 점이 핵심 함정. Phase 1-3 smoke 1차에서 expand=150이 reasoning 128 + output 0으로 빈 응답 → token 한도 상향 + `reasoning=minimal` 강제로 해결.
- Phase 1-7에서 1회 `/graduation/audit`가 7개 G-citation 포함된 1.2KB 응답을 ~600 output tokens로 생성 → output 한도 여유 충분.
- 의외로 polish 노드가 비용 단가 가장 큼(긴 답변 본문 다듬기). 데모 외 시간 OFF 권장.
