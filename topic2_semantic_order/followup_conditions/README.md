# Semantic interleaving: failure conditions

현재 상태: 기존 결과 CPU 진단 및 반복 재분석 완료, 새 순서와 20개 config/gates 완료. 신규 GPU 학습·평가는 **BLOCKED**. Experiment 4는 승인 전 준비만 했다. 원래 결과와 H-final 봉인은 유지한다.

- [사전등록](EXPERIMENT_PLAN.md) · [실험 매트릭스](EXPERIMENT_MATRIX.md) · [감사](DATA_AND_CONFIG_AUDIT.md)
- [기존 결과 진단](EXISTING_RESULT_DIAGNOSTICS.md) · [결과](RESULTS.md) · [통계](STATISTICAL_ANALYSIS.md)
- [실패 조건](FAILURE_CONDITIONS.md) · [논문 문구](PAPER_FINDINGS.md) · [다음 실험](NEXT_EXPERIMENTS.md)

저장소 root에서 실행한다. 아래 명령은 CPU 전용이며 승인되지 않은 coverage, 평가 추론, GPU를 호출하지 않는다. 전체 분석은 원본 V4와 기존 저장된 eval 결과에 의존한다.

```bash
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export HF_HOME=/data/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
p=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
f=topic2_semantic_order/followup_conditions
(cd "$f" && sha256sum -c PREREGISTRATION.sha256)
"$p" "$f/evidence_audit.py"
"$p" "$f/token_ledger.py"
"$p" "$f/exposure.py"
"$p" "$f/regression.py"
"$p" "$f/explore.py"
"$p" "$f/figures.py"
"$p" "$f/prepare.py"
"$p" "$f/make_jobs.py"
"$p" "$f/verify.py"
"$p" "$f/test_followup.py" -v
PYTHONPATH=topic2_semantic_order "$p" -m unittest topic2_semantic_order.test_semantic_schedule -v
"$p" "$f/analyze_new.py"
"$p" "$f/launch.py" --phase 1
"$p" "$f/launch.py" --phase 2
```

Baseline commit `5d6a257608c7b016b876cf5c25004879d02f6ade`, 사전등록 commit `7f0853fa953e1b009ea1a08ffb83d1667cf405d4` 및 [문서 SHA](PREREGISTRATION.sha256). [설정·순서 SHA 목록](configs/manifest.json), [Phase 1 job manifest](gpu/jobs_phase1.json), [Phase 2](gpu/jobs_phase2.json). 출력에 기록하는 것은 optimizer 업데이트 직전 LR이다. Token ledger는 실제 TRL labels 기반이다.

## GPU 실행 승인 후

이번 실험에 대한 새 승인에 **단일 물리 GPU UUID, 승인 범위(phase), 새 작업 시작 마감 KST**, 장시간 작업을 위한 실행 허용 시간을 명시한다. 기본 장치 후보는 workstation4 `GPU-48f798cc-9437-50ac-d604-448bbad7b311`(관측 index 2). 현재 spare UUID는 조회되지 않았다. Phase 1은 12 train + 216 eval cells, 순수 직렬 약 85 GPU-hours. Phase 2는 8 train + 144 cells, 약 56.7 GPU-hours. 추정은 기존 처리시간 기반이며 재시도는 별도다. 옛 실험 승인으로 새 실행을 열지 않는다. 시작 전 host GPU 상태·타 사용자 프로세스·Ollama 컨테이너/device 및 API 상태·torch UUID를 재확인한다.

동결된 실행 커밋을 별도 worktree로 checkout하고, 새 승인 내용을 외부 JSON으로 보존한다. 키는 `commit` (full SHA), `manifest_sha256` (실행 대상 파일), `gpu_uuid`, `start_before` (ISO 8601, timezone 필수). 승인이 없으면 이 JSON을 임의로 생성하지 않는다. 승인된 시각을 넘겨 새 train/eval cell을 시작하지 않으며 이미 실행 중인 cell의 완료는 고려해야 한다. 아래는 승인 후 실행 템플릿이다.

```bash
p=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
f=topic2_semantic_order/followup_conditions
git worktree add --detach "$FOLLOWUP_WORKTREE" "$FOLLOWUP_COMMIT"
cd "$FOLLOWUP_WORKTREE"
"$p" "$f/launch.py" --phase 1 --approval "$FOLLOWUP_APPROVAL" --run
```

승인 범위에 phase 2가 포함되면 phase 1 기술 검증 후 같은 방식으로 `--phase 2`를 사용한다(해당 phase manifest SHA의 승인 레코드 필요). 러너는 GPU별 train/eval을 순차 실행하고 CT10K/H-dev/E1의 동결 harness를 그대로 사용한다. 산출물은 원래 checkout의 이 디렉터리 아래 `gpu/execution/`, `cells/`, `cells_raw/`에 생성된다. Adapter와 체크포인트 및 adapter SHA 기록은 외부 `/data/hwkim/sftdpo_work/topic2_semantic_order/followup_conditions/`에 유지한다. GPU 실행 이력이 없으므로 지금은 GPU 학습/평가 로그와 신규 원본 셀이 없다.

[Coverage 계획](coverage/COVERAGE_PLAN.md)은 새 학습이나 신규 teacher trace 생성 없이 감사 요건과 validator만 제공한다.
