# Reviewed gold v003

사용자의 명시적 batch003 정책 승인에 따라 v002를 확장했다. Semantic review draft의 권고나 Validator PASS를 자동 승인으로 취급하지 않았다. 개별 항목을 사용자가 직접 열어 검토했다는 주장은 하지 않는다. 승인 근거와 Codex의 위임 검증을 각 decision에 기록했다.

- Accepted: RB003-03–20 SFT 18건, RB003-23–34 DPO 12건, 총 30건.
- Diagnostic: RB003-01/02. 보호된 RPM 평균 family의 원본 tool-text 근거를 유지했다.
- Hold: RB003-21/22. raw contract 오류와 normalization 이후 의미가 혼합되어 있어 pair로 export하지 않았다.
- Workflow의 실제 status는 accepted 30 / needs_fix 4다. 비승인 4건은 `corpus_disposition`으로 hold 2 / diagnostic_only 2를 구분한다. Queue의 원래 pending status와 draft는 변경하지 않았다.

v001/v002와 모든 보호 원본, production prompt/schema/runtime, 기존 training config는 byte/hash 검증으로 보존했다. GPU inference/training, provider 실행, 시스템 설정 변경은 수행하지 않았다.

## 고정 corpus와 split

| Corpus | SFT train / valid | DPO train / valid | Semantic / constraint pairs |
|---|---:|---:|---:|
| v002 | 12 / 5 | 16 / 4 | 11 / 9 |
| v003 | 19 / 16 | 18 / 14 | 21 / 11 |

기존 레코드는 각 split의 동일한 prefix로 남긴다. 신규 split은 검토 이전 `split_plan.json`의 seed 42 예약을 그대로 사용했다. 신규 DPO는 train의 실제 pilot 오답 constraint 2건과 valid의 검토된 synthetic semantic contrast 10건이다. 모든 32개 pair의 prompt/chosen은 같은 split의 실제 승인 SFT와 일치한다. 신규 chosen dependency는 먼저 실제 accepted decision/hash가 존재하는지 확인했다.

신규 validation family 5개, semantic fingerprint 9개:

- `rb003-rpm-week-median-mean-date-contrast`: 03/04, 날짜 factor와 RPM 주별 median→mean.
- `rb003-fare-month-max-mean`: 06, fare 월별 max→mean.
- `rb003-speed-month-stage-validation`: 08/11/12, speed inner/outer와 literal scope/place, source/role/value contrast.
- `rb003-od-two-filters-emd-bottom`: 15/16/17, 두 endpoint filter와 pickup/dropoff/both dimension_target.
- `rb003-fare-month-min-max-answer-contrast`: 19/20, fare 값 반환과 해당 month dimension 반환.

Measure 수는 fare 1→6, speed 1→5, rpm 1→4, revenue 4→5, trip_count 5→10이다. passage_count/vacant_ratio와 명시적 unsupported gold는 여전히 비어 있다. 검토 승인과 TIMS/provider 실행 가능성은 별도다. 신규 합성 place/scope gold는 execution benchmark에서 제외한다. 기존 execution exclusion과 RB001 hold 정책은 유지한다.

## Strict 검증

`sft_record`, `dpo_pair`, `assess`, 기존 parser/composer/G1–G7 Validator, `pilot.audit`, trainer `load_records`를 재사용했다. 별도의 validator는 만들지 않았다. Gold 35건은 normalize=False/True 모두 통과했다. Reject는 의도된 constraint failure를 허용하고 의미 오류의 근거를 별도 기록했다. Parent/question/template/family 및 chosen/rejected contrast family의 split 교집합이 없다. 기존 보호 validation을 training으로 이동하지 않았다.

`strict_validation.json`, `lineage_audit.json`, `pair_validation.json`, `coverage_before_after.json`, `dpo_distribution.json`이 상세 결과다. 새 validation 및 그 preference contrast와 diagnostic family의 protection fingerprints도 보존한다.

## Token-limit: 승인과 학습 가능성은 별도

Pinned Qwen/Qwen3-8B revision `b968826d9c46dd6066d109eabc6255188de91218`의 실제 tokenizer와 production chat template을 CPU/offline에서 재측정했다. Generation prefix, JSON completion, EOS를 포함한다. 기존 trainer는 합계에 +1 guard를 적용한다. `token_validation.json`에 tokenizer/template/config/source hashes와 전체 분포, `token_lengths.jsonl`에 67개 export record 길이가 있다.

| ID | 실제 최대 sequence tokens (EOS 포함) | Trainer 필요 길이 (+1) | Prompt |
|---|---:|---:|---:|
| RB003-13 | 6969 | 6970 | 6780 |
| RB003-14 | 6969 | 6970 | 6779 |
| RB003-15 | 6969 | 6970 | 6782 |
| RB003-16 | 6969 | 6970 | 6781 |
| RB003-17 | 6976 | 6977 | 6789 |
| RB003-24 | 6934 (rejected) | 6935 | 6750 |
| RB003-30 | 6977 (rejected) | 6978 | 6789 |

현재 SFT/DPO total 6912에서 위 7건이 차단된다. DPO 30은 prompt 6784도 초과한다. 승인된 모든 sample을 보존했고 truncate/drop은 0건이다.

최소 안전 limit은 SFT `max_seq_length=6977`, DPO `max_length=6978`, `max_prompt_length=6789`, completion 최소 188이다. 기존 completion 256은 충분하다. 기존 analyzer의 128 단위 반올림 권고는 total 7040 / prompt 6912 / completion 256이며, 정확한 최소치와 구분한다. 최소 limit을 메모리상의 검증용 config copy에만 적용했을 때 모든 record가 기존 `render_records`를 통과했다. 어떠한 training config 파일도 변경하지 않았다. GPU memory 적합성을 입증한 결과는 아니다.

다음 단계는 token limit 조정 후보를 사용한 Thor memory smoke다. 이 작업에서 학습을 시작하지 않는다.

## 저장과 재구성

운영 산출물: `training/annotations/generated/corpora/reviewed_gold_v003/`; 최종 receipt: `training/annotations/generated/review_batch_003/decisions_003.jsonl`. Ignored 생성 디렉터리는 commit하지 않았다. 여기에는 작은 text evidence와 production prompt를 hash marker로 치환한 `dataset_index.json`을 보존한다. 반복되는 거대한 prompt가 포함된 training JSONL, binary, weights/checkpoints는 commit하지 않는다.

Fresh clone에서도 현재 production prompt hash가 같으면 아래 CPU-only 명령으로 정확히 같은 4개 dataset JSONL와 manifest를 재구성할 수 있다. 파일 hash와 split을 재검증하며 기존 출력은 덮어쓰지 않는다. 승인이나 새 candidate 생성은 하지 않는다.

```bash
python -m training.records.corpora.reviewed_gold_v003.assembly_recipe \
  --restore-from training/records/corpora/reviewed_gold_v003 \
  --output training/annotations/generated/corpora/reviewed_gold_v003
```

`assembly_recipe.py`의 원래 확정 경로는 이 batch에 대한 사용자 정책과 archived queue/draft hash에 한정된다. 다른 batch를 자동 승인하는 일반 importer가 아니다. 재확정 경로는 기존 최종 corpus/decision을 덮어쓰지 않는다. 현재 config를 위 export로 연결하는 작업과 limit 변경은 후속 Thor smoke 단계에서 한다.
