# GPU execution status

Initial read-only host check on workstation4, 2026-11-13 KST. All three GPUs reported 15 MiB used / 49,140 MiB and the compute-app query returned no rows. The default physical GPU `GPU-48f798cc-9437-50ac-d604-448bbad7b311` was index 2. The policy spare `GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21` was not present. Docker listed no `ollama` container and `localhost:11434/api/ps` returned connection refused. No process or container was changed. No CUDA context was created for a follow-up job. This observation is not a reservation and must be refreshed before an approved run.

At that initial check, task-specific GPU allocation was pending. Historical decision 264/job manifests and subsequent retraining allocations apply to their original runs. [Phase 1](preview_phase1.json) and [phase 2](preview_phase2.json) previews validate only manifest structure, estimates and CPU gates. The previews preceded GPU execution. Coverage requires separate human data approval.

## Three-GPU allocation, 2026-11-13 KST

The user approved proceeding and using all three workstation4 GPUs. Run phases 1 and 2 in the registered order. One GPU owns each order seed and runs its new arms serially. The five-item device comparison uses the same existing B-o2026113 adapter, H-dev items and sampling seeds on all three devices. Historical A/B evaluations were collected previously, on the devices recorded in their original metadata. The probe tests this serving configuration on these items and does not establish cross-device training equivalence. The default seven-day start cutoff is an operational choice that allows headroom for the estimated 57 hours and reruns.

At 07:11 KST, C training started on all three devices. The device probe produced five calls on each device. Both non-reference devices differed from the reference in raw response bytes. The test includes separate vLLM server starts, so it cannot isolate hardware from serving nondeterminism.

The same-GPU baseline plan reuses 70 of 180 historical A/B cells. The other 110 cells (40 CT10K, 5 H-dev and 65 E1) will be measured on the assigned GPU using the verified original adapters. The launcher schedules these measurements after the registered treatment runs. The historical A/B analysis is retained as a sensitivity analysis. The same-GPU estimates use the same contrasts, endpoints, seeds and bootstrap rules. Historical base samples used to define collapse thresholds stay fixed.

## Idle GPU backfill, 2026-11-15 KST

Phase 1 GPU 1 released at 08:50 KST. GPU 1 began the already planned matched B-o211102 E1 aux cells at 13:30 KST with the original evaluator and adapter, under `topic2-baselines-idle1-1886ead0.service`. Its dispatch wrapper is pinned at `1886ead0`, and scored cell provenance stays at baseline evaluator commit `215b2dd0`. The existing GPU 0 and GPU 2 treatments continued.

The wrapper's CPU checks verified all ten historical adapter digests and the full 110-cell baseline manifest. Phase 2 reserves GPU 0 and GPU 1, leaving 34 already planned A/B cells eligible for early dispatch on GPU 2. The action to install the early dispatch and replace the waiting baseline trigger was rejected by automatic approval review. The original trigger remains queued, and the GPU 2 early dispatch remains pending. The pending original launcher has a missing `pathlib.Path` import in `run_gpu`. The new wrapper resolves the checkpoint path and runs the same pinned evaluator. Successful final dispatch publishes the existing `matched_baselines/done.json` receipt for the scheduled analyses.

The user then approved the trigger replacement. At 13:32 KST, the two new path units were verified waiting, and the original waiting path was stopped while its service had no process. `topic2-baselines-idle2-1886ead0.path` dispatches the 34 assigned GPU 2 cells on `phase1_done.json`. `topic2-baselines-complete-1886ead0.path` dispatches the remaining cells on `phase2_done.json` once any early services have exited. It reuses validated cell receipts and publishes the original completion marker. The E1/E2 launcher and the downstream analysis, taxonomy, and Option B units were active under their existing schedules. At that check all three GPUs were occupied, and GPU 1 had produced its first validated backfill cell.

## 장치별 승인 큐 전환, 2026-11-15 KST

14:28에 GPU 1의 vLLM PID 1929339를 확인했다. `/proc/1929339/cgroup`과 systemd ControlGroup이 `topic2-baselines-idle1-e1-9d5847ad.service`로 일치했다. 기존 GPU 서비스는 계속 진행했다. 실행된 A/B 평가의 commit은 `215b2dd0`이고 새 큐 운영 코드는 별도 worktree에 `d44abd45`로 고정했다.

14:33 현재 새 `topic2-device-baselines-*-d44abd45.path` 5개는 대기 상태이며 CPU dispatcher가 실제 평가 증빙 갱신에 반응해 정상 종료한 것을 확인했다. 기존 A/B 경로 두 개는 해당 서비스의 PID가 0일 때만 해제했다. 새 dispatcher는 원래 장치 배정과 `job_completed` 증빙을 대조한다. GPU 2는 자기 1단계 종료 후 34셀을 시작하고, GPU 0·1은 각자의 2단계 완료 후 같은 장치의 남은 A/B를 시작한다. GPU 1은 현재 E1이 끝났고 다른 장치의 대기 구간이 충분한 경우 이미 할당된 H-dev 1셀을 앞당긴다. E1/E2의 원래 1→2단계 전환 기준과 후속 분석/B안 시작 조건은 유지했다.

| GPU | 1단계 평가 잔여 | 2단계 학습 및 평가 | 미검증 A/B 평가 셀 | A/B 완료 예상 |
|---|---:|---:|---:|---|
| 0 | 13 | 학습 4개, 평가 72셀 | 42 | 11월 18일 밤 |
| 1 | 0 | 학습 4개, 평가 72셀 | 29, 진행 중 포함 | 11월 19일 새벽 |
| 2 | 10 | 0 | 34 | 11월 16일 오후 |

예상은 관측된 학습 중앙값과 평가별 중앙값·재시도 비율에 근거하며 진행 중인 셀의 경과시간은 별도로 차감하지 않았다. GPU별 승인 작업을 모두 마친 뒤의 대기는 고정 장치 배정에서 발생할 수 있다. 실측된 스케줄 개선의 완료 여부는 lane별 종료 증빙을 받은 후 기록한다.

장치별 시작·완료 증빙은 `gpu/execution/matched_baselines/device_queue/`에 생성한다. 이미 완료된 셀은 SHA와 UUID가 맞을 때 제외하고 장치별 잠금으로 중복 시작을 막는다. 모든 장치가 처리한 셀을 검증한 뒤 `matched_baselines/done.json`을 원자적으로 한 번 발행한다. 이후 dispatcher는 실행 요청 없이 종료한다. 기존 분석과 B안이 이 완료 증빙을 이어받는다.

## 1단계 완료와 장치별 전환

2026-11-15 21:21:37 KST에 E1/E2 1단계 12개 실행의 평가 216셀이 모두 완료됐다. 기존 실행기가 같은 시각 GPU 0에서 `C-o2026117`, GPU 1에서 `C-o2026131`을 시작했다. 장치별 스케줄러는 GPU 2의 `lane2.ready`를 발행했고, GPU 2의 첫 A/B 평가가 21:22:31에 시작됐다. 22:01 직접 점검에서 세 장치가 실행 중이었고 승인 A/B 24셀이 검증됐다. 기존 Phase 1 대기 중에는 19:01, 19:16, 19:31, 19:46에 GPU 0의 배정된 E1 셀을 수동으로 앞당겼고, 2단계 전환이 가까울 때는 새 작업을 시작하지 않았다. 수동 선택 wrapper는 `400ebad6`에 고정했다.
