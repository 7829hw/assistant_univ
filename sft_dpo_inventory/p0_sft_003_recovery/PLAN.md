# P0 full-reasoning 데이터 회수 1단계: 사전 등록

고정: 2026-10-14, 모델 호출 전. 결정 72.

- 기존 missing 84(M1 59, M2 21, M3 4)와 우선순위(P1 30, P2 17, P3 37)는 `p0_sft_003_prep/missing_reasoning_manifest.json` 그대로다.
- R70 70과 기존 trace 승인·거부 판정은 바꾸지 않는다. p0_sft_001·002·003_prep 파일은 고치지 않는다.
- 하지 않는 것:
  - 27B 다운로드·pull·import·호출
  - 새 SFT, DPO, 새 prompt, P0.4
  - pruning, quantization
  - R70 403 평가

## 1. M3 재검사(`m3_recovery.py`, 모델 호출 없음)

- **대상**: b004-19, b005-19, b006-10, b006-11.
- 문항의 EXACT_OR_SEMANTIC_MATCH trace(기존 `traces.jsonl`) 중 기존 필터에서 빠진 것을 모두 본다.
- **기록 항목**:
  - correct trace 수, 탈락 이유(결정 4 tokenize 왕복 / 40-D 루프 / 18 길이)
  - thinking·최종 응답 존재, truncation(done_reason), EOS
  - 왕복 불일치 위치(첫 다른 token 위치와 앞뒤 문자열)
- **RECOVERABLE**(모두 만족):
  1. done_reason stop, `</think>` 닫힘, thinking 비어 있지 않음
  2. 원문을 다시 tokenize해 decode하면 원문 문자열과 바이트 단위로 같다. 즉 불일치가 같은 문자열의 token 분할 차이뿐이다.
  3. 생성 token 끝이 EOS(`<|im_end|>`)다.
  4. 판정이 EXACT_OR_SEMANTIC_MATCH다.
  5. 루프·길이 필터에는 걸리지 않는다.
- 그 밖(token 손실, 잘림, EOS 손상, 경계 손상, 문자열 변형)은 NOT_RECOVERABLE이다.
- 이 진단은 M3 4문항에만 한다. 기존 307개에 새 filter를 소급 적용하지 않는다. filter 정책 변경은 별도 결정이다.
- RECOVERABLE trace가 여러 개인 문항은 3절 ranking으로 1개를 고르고 4절 사람 검토를 한다.

## 2. M2 8B 추가 sampling(`m2_sample.py`)

- **대상 21**(정렬 순서 = m2_index 0–20):
  - 앞 10: ann-29dcb56f51da6d6a361f, ann-f78087861d0826ae8a7f, b004-18, b004-22, b004-40, b005-04, b005-33, b005-34, b005-36, b005-41
  - 뒤 11: b005-54, b005-58, b006-02, b006-04, b006-08, b006-13, b006-14, b006-18, b006-19, b006-28, b006-34
- **모델**: HF `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`(tokenizer 같음)
  - BF16·SDPA, `HF_HOME=/data/hwkim/path_repeat_001/hf-cache` offline. 새 다운로드 없음, Ollama 없음.
- **prompt**: P0(hash `d7f4c12a`), 입력은 v006 레코드의 [system, user].
- **생성**:
  - `enable_thinking=True`, max_new_tokens 8192, sampling만(greedy 다시 안 함)
  - temperature 0.6, top_p 0.95, top_k 20(기존 수집과 같음)
  - 문항당 표본 8개를 기존 수집과 같은 방식(한 번의 generate, num_return_sequences 8)으로 만든다. 21 × 8 = 168.
- **seed**: `2026101400 + m2_index`.
  - 기존 `20261006 + 순번`(20261006–20261159)과 겹치지 않는다.
  - 표본 번호 k = 1–8은 그 generate 안의 순서다. 같은 문항은 다시 돌려도 같은 seed다.
- **저장**(`training/generated/p0_sft_003_recovery/m2_raw/traces.jsonl`, 결정 33에 따라 커밋):
  - item_id, question, model·revision, prompt hash, batch seed·sample index, 생성 설정
  - raw_text, thinking 원문, 최종 응답, parsed, 판정 범주
  - 생성 token 수, thinking 글자·token 수, 생성 token id
- **판정**: `collect_p0_traces_hf.judge` 그대로(5범주).
- **1차 필터**: EXACT_OR_SEMANTIC_MATCH, thinking 있음, truncation 없음, 결정 4 왕복·40-D 루프·18 길이 통과(기존 정책 그대로).
- **중단 조건**: 기반 장애(crash·OOM·GPU 오류)만. 결과를 보고 sample 수·temperature·top_p를 바꾸거나 M1으로 넓히지 않는다.

## 3. clean-trace ranking(결과 전 고정, M2·M3 같음)

- wrong-value mention은 `p0_sft_003_prep/trace_quality_analysis.py`의 `wrong_mentions` 그대로다.
  - 대상 field: measure, dimension, dimension_target, od_role, aggregation, rollup, bucket, unsupported
- 큰 번복의 근사 지표는 "Wait"·"Hmm" 출현 수(wait_hmm)다.

| Tier | 이름 | 조건 |
|---|---|---|
| 1 | CLEAN_DIRECT | wrong-value mention 없음, wait_hmm ≤ 2 |
| 2 | MINOR_SELF_CORRECTION | wrong-value mention 없음, wait_hmm > 2 |
| 3 | SELF_CORRECTED | wrong-value mention 있음. 상위 tier가 없을 때만 후보 |

- 같은 tier 안에서는 다음 순서로 고른다.
  1. wrong-value field 수 적은 것
  2. hedge 수 적은 것
  3. thinking 짧은 것
  4. sample index 작은 것
- 문항당 1개만 고른다.

## 4. 사람 기준 검토(Claude, 문항당 선택 trace 1개)

- 판정: APPROVE_TRACE / REJECT_TRACE. decision, reason, quality tags를 남긴다.
- 거부 기준(p0_sft_001 TRACE_REVIEW 기준 + 지시 19절):
  - 묶음 단위어를 place·concept로 해석함
  - aggregation 값을 잘못 말했다가 답만 맞음
  - dimension_target을 잘못 말했다가 마지막에만 고침
  - od_role과 dimension_target을 혼동함
  - unsupported로 결론 낸 뒤 JSON만 맞음
  - 없는 ontology 규칙을 사용함
  - 추론의 결론과 답이 충돌함
  - Full 잔재가 추론을 지배함
  - 단순한 문장 망설임만으로는 거부하지 않는다.
- 거부되면 그 문항은 M2_RECOVERY_FAILED(M3는 M3_RECOVERY_FAILED)다. 다른 표본으로 바꾸지 않는다.

## 5. M1과 27B

- M1 59에는 8B 추가 sampling을 하지 않는다.
- 27B 대상 = M1 AND priority ∈ {P1, P2}(예상 31). manifest에서 다시 계산한다. M2 결과를 보고 대상을 바꾸지 않는다.
- 27B 반입·호출은 하지 않는다(별도 사용자 승인).
- 반입 계획은 `TEACHER27B_IMPORT_PLAN.md`에 적는다.
  - 과거 승인 teacher(Ollama `qwen3.8:27b`, digest `aaee06c39dcf…`, Q4_K_M)의 기록을 확인해 쓴다.
- **향후 teacher 생성 계획(승인 뒤 실행)**:
  - P0 prompt, think 켬, gold를 주지 않음
  - 문항당 greedy 1 + sampling 4(temperature 0.6, top_p 0.95, top_k 20), 최대 155 호출
  - Ollama 문항 격리는 unload_per_question(CLAUDE.md 14번)
  - 판정·필터·ranking·사람 검토는 위와 같다.
  - 과거 teacher 정책(sampling 8, temperature 0.6)보다 표본이 적다. 학습 사용 상한(질문당 4, 결정 48·50)과는 충돌하지 않는다.

## 6. coverage와 provenance

- `coverage_manifest.json`: R70 70 + 회수 M3 + 회수 M2(unique item 기준)
  - reasoning-covered / 154를 낸다.
  - feature별 coverage: dt pickup·dropoff·both, od_ne_dt, Gap A·B, bucket, order, emd, sido, sigungu, h3
- trace provenance: teacher_model, teacher_revision, generation_batch, seed, quality_tier, review_decision.
- 최종 reasoning dataset(`reviewed_reasoning_v001` 등)은 아직 freeze하지 않는다.

## 7. scope 역조회·refusal

- 추가하지 않는다. `known_uncovered_family`로 남긴다.
- v006의 compile 정지·unsupported·needs_clarification 표현 inventory만 기록한다. batch007 후보로 둔다.
