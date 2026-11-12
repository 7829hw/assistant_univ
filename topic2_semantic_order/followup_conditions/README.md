# Semantic interleaving: failure conditions

현재 상태: 기존 결과 CPU 진단 및 반복 재분석 완료, 새 순서와 20개 config/gates 완료. 신규 GPU 작업의 현재 상태는 [실행 기록](gpu/STATUS.md)에 있다. Experiment 4는 승인 전 준비만 했다. 원래 결과와 H-final 봉인은 유지한다.

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

2026-11-13 사용자 지시로 workstation4의 GPU 3장(현재 인덱스 0, 1, 2)을 사용한다. UUID, 두 phase의 manifest SHA, 실행 커밋, 새 작업 시작 마감(KST)은 실행 기록에 남긴다. 같은 order seed의 신규 조건 4개는 한 장치에 고정한다. 각 장치에서 같은 adapter와 seed로 H-dev 5문항을 생성해 호출별 UTF-8 응답을 비교한다. Phase 1의 3개 seed를 마친 뒤 Phase 2의 2개 seed로 넘어간다. 기존 처리시간 기준 1단계 약 28 GPU 벽시계 시간, 2단계 약 28시간이 예상된다. 재평가와 서버 초기화는 별도다.

실행은 별도 detached worktree에서 한다. GPU 배정 기록의 키는 `commit`(full SHA), `manifest_sha256`(phase 번호별 SHA 매핑), `gpu_uuids`(장치 UUID 목록), `start_before`(timezone이 있는 ISO 8601)다. 이 시각 이후에는 새 train/eval cell의 시작을 막는다. 아래는 승인 후 실행 템플릿이다.

```bash
p=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
f=topic2_semantic_order/followup_conditions
git worktree add --detach "$FOLLOWUP_WORKTREE" "$FOLLOWUP_COMMIT"
cd "$FOLLOWUP_WORKTREE"
"$p" "$f/launch.py" --phase 1 2 --approval "$FOLLOWUP_APPROVAL" --run
```

각 GPU는 작업 하나씩 실행하고, CT10K/H-dev/E1에는 동결된 평가 코드를 사용한다. 산출물은 원래 checkout의 이 디렉터리 아래 `gpu/execution/`, `cells/`, `cells_raw/`에 생성된다. Adapter와 체크포인트 및 adapter SHA 기록은 외부 `/data/hwkim/sftdpo_work/topic2_semantic_order/followup_conditions/`에 유지한다. 장치 비교는 `gpu/execution/device_probe/`, phase별 GPU 배정과 학습·평가 기록은 `gpu/execution/`에 저장된다.

[Coverage 계획](coverage/COVERAGE_PLAN.md)은 새 학습이나 신규 teacher trace 생성 없이 감사 요건과 validator만 제공한다.
