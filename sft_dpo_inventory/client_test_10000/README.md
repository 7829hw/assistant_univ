# client_test_10000 — pilot_010 V4 10,000문항 테스트(2026-10-29, 사용자 지시)

사용자 지시(2026-10-29): 업로드한 `qa_test_10000.yaml`로 HF 경로의 파인튜닝 모델(pilot_010 결과)을 GPU 3장 모두 써서 테스트한다.
사용자 선택: pilot_010에서 고른 변형 V4의 순서 seed adapter 3개(o43·o1016·o7)를 GPU마다 하나씩, 10,000문항 전체를 k=1로 잰다.

## 문항

- `qa_test_10000.yaml`: 업로드 원본(`/home/hwkim/.claude/uploads/12d76b1a-6be5-41c3-a142-fd1ebc672a67/11a3b793-qa_test_10000.yaml`)을 바이트 그대로 복사.
  sha256 `0fcbf02cba8043a8d4d52cc6ed39c87e910b7ed8fa05cb9cbe75b2de89d9795b`. 원천 `llm-finetuning-30000.jsonl`(sha256 `63d445b8…`), seed 20261029 층화 추출.
- 파일 note대로 **평가 전용**: 학습·checkpoint 선택·annotation 후보에 쓰지 않는다. 최종 판정 셋(protected_final)이 아니다.
- 10,000문항 모두 `expected_outcome: answered`(거부 문항 없음). pool: vendor100_date_variant 5,272 · independent 3,749 · train_skeleton 967 · verbatim_vendor100 12.
- `gpu/chunks/c1–c5.txt`: 문항 파일 순서대로 2,000문항씩 나눈 id 목록(셀 파일 단위).

## 측정 조건

- 모델: base Qwen3-8B@b968826d BF16 + LoRA `S-V4-<seed>/checkpoint-1984`(`/data/hwkim/sftdpo_work/pilot_010/train_s10/`, sha256은 `pilot_010` 기록과 같음:
  o43 `a3a1222f…`, o1016 `1a25e096…`, o7 `e715e055…`). vLLM 서빙(`pilot_007/gpu_data/serve7.sh`, flashinfer, max-model-len 17,408), thinking ON, 프롬프트 87048d0c.
- client·채점: `pilot_006_prep/gpu_data/run_cell6x.py` → `pilot_005/vllm_eval_thinking5.py`(pilot_010 셀과 같음), grounding_target full, 기준일 2026-09-25.
  sampler temperature 0.6 · top_p 0.95 · top_k 20 · min_p 0, seed-base 20261100(k=1 → 회차 seed 20261101).
- pilot_010 셀과 다른 점: 동시 요청 32(pilot_010은 8). 이 테스트는 pilot_010 셀과 직접 비교하는 판정이 아니다.
- 작업 하나 = GPU 하나(결정 114): CT10K-o43 / CT10K-o1016 / CT10K-o7. 실행은 `gpu/run_ct10k.sh SEED GPU PORT`, 이 디렉터리가 들어간 커밋에 고정한 worktree에서.
  서버 기동 때 `gpu_ok`(host nvidia-smi UUID·메모리·다른 프로세스, torch UUID, Ollama GPU면 `/api/ps` 비어 있음)를 확인한다. 기록 `gpu/runs.log`·`gpu/gpu_check.txt`·`gpu/timeline.jsonl`·`gpu/server_CT10K-*.json`.

## 출력

- 셀: `cells/ct10k_v4_<seed>_c<1-5>_s1.json`·`.log`. 원문: `training/generated/client_test_10000/raw/`.
- 결과 요약은 측정이 끝난 뒤 `RESULTS.md`에 적는다.
