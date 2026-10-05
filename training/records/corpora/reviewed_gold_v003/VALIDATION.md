# V003 확정 검증

확정 기준 commit: `7ebca865248afc0f48bcfdb4d92f790a7eb7c6a8`, branch `geoflow/sft-dpo-thor`, seed 42. 이 문서는 최종 데이터 commit 이전 검증 결과다. Parent corpus, prompt와 ontology/factor/runtime definitions, 원본 queue/draft, 보호 source, 모든 기존 training config의 hash를 assembly 전후 대조했다. 기존 v001/v002와 review/RB001 hold는 수정하지 않았다.

## 실행 결과

- 최종 decision 34건: accepted 30, hold 2, diagnostic_only 2. 각 receipt checksum/candidate checksum/dependency decision hash 검증 완료.
- SFT 35건: train 19 / validation 16. `sft_record` strict flat serialization, parse → compose → G1–G7 validate와 production normalization 모두 통과.
- DPO 32건: train 18 / validation 14. 모든 chosen의 승인 SFT/prompt/동일 split 일치, chosen != rejected, unique pair 통과. 신규 pair에는 canonical chosen SHA256와 승인 decision hash를 기록했다.
- DPO 전체 semantic 21 / constraint 11. Train 8/10, valid 13/1. 신규 actual failure constraint 2 / reviewed synthetic semantic 10.
- Parent/question/template/semantic family와 preference contrast family의 train/valid 교집합 0. Protected train-origin 검사 통과. Validation/diagnostic-origin prediction을 training으로 옮기지 않았다.
- 기본 TIMS/provider 실행 또는 GPU smoke는 실행하지 않았다. Validator PASS는 사용자 semantic 승인 근거를 대체하지 않는다.
- Offline cached Qwen3 tokenizer로 전체 SFT 35 + DPO 32개 record를 측정했다. 7개 token blocker를 보존했으며 현재 limit에서 renderer가 fail하는 것도 확인했다. 메모리상 검증용 최소치에서 67/67 render 통과. Config 파일 변경, truncate, drop은 0.

## Tests

CPU-only 개발 검증 interpreter: `/tmp/geoflow-training-venv/bin/python`. 이 환경에는 torch가 없으며, tokenizer 측정에는 transformers/tokenizers만 사용했다. Thor GPU 환경을 검증한 결과로 해석하지 않는다.

```bash
python -m unittest discover -s tests -p 'test_training*.py'
python -m unittest discover -s tests
python -m training.records.corpora.reviewed_gold_v003.assembly_recipe --help
python -m training.records.corpora.reviewed_gold_v003.assembly_recipe \
  --restore-from training/records/corpora/reviewed_gold_v003 \
  --output /tmp/geoflow-v003-exact-replay
```

- 관련 training suite: **120 tests, OK (skipped=2)**, 21.485s. 신규 v003 회귀 테스트 12개 포함.
- 전체 suite: **1178 tests, OK (skipped=2, expected failures=1)**, 68.276s. 전체 suite의 localhost socket 테스트 때문에 sandbox 외 실행을 사용했다. 네트워크 서비스/GPU 학습은 실행하지 않았다. 기존 socket ResourceWarning은 실패가 아니다.
- CLI `--help` 및 exact export replay 성공. 재구성된 SFT/DPO JSONL 4개는 corpus manifest의 원본 dataset hash와 일치한다. 승인 추가나 queue/status 변경이 없는 replay다.
- 원래 `training/records/snapshot_manifest.json`의 94개 역사적 snapshot hash 모두 유지.

## 다음 gate

현재 config에서 total 6912 때문에 RB003-13–17/24/30이 막힌다. RB003-30은 prompt 6784도 초과한다. 최소값 SFT 6977, DPO total 6978/prompt 6789, completion 188; 기존 completion 256 유지 가능. 단위 반올림 profile을 선택한다면 기존 analyzer는 total 7040/prompt 6912/completion 256을 권고한다.

**다음 작업은 token-limit 조정 후보 + Thor memory smoke**다. 기존 BF16 LoRA rank16/SDPA/checkpointing/AdamW 경로를 유지한 상태에서 실제 backward/optimizer step과 memory를 측정한 뒤 config 변경을 확정해야 한다. 이 corpus 확정만으로 현재 config에서 pilot 실행 준비가 완료되었다고 주장하지 않는다.
