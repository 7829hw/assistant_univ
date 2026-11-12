# GPU execution status

Initial read-only host check on workstation4, 2026-11-13 KST. All three GPUs reported 15 MiB used / 49,140 MiB and the compute-app query returned no rows. The default physical GPU `GPU-48f798cc-9437-50ac-d604-448bbad7b311` was index 2. The policy spare `GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21` was not present. Docker listed no `ollama` container and `localhost:11434/api/ps` returned connection refused. No process or container was changed. No CUDA context was created for a follow-up job. This observation is not a reservation and must be refreshed before an approved run.

At that initial check, task-specific GPU allocation was pending. Historical decision 264/job manifests and subsequent retraining allocations apply to their original runs. [Phase 1](preview_phase1.json) and [phase 2](preview_phase2.json) previews validate only manifest structure, estimates and CPU gates. The previews preceded GPU execution. Coverage requires separate human data approval.

## Three-GPU allocation, 2026-11-13 KST

The user approved proceeding and using all three workstation4 GPUs. Run phases 1 and 2 in the registered order. One GPU owns each order seed and runs its new arms serially. The five-item device comparison uses the same existing B-o2026113 adapter, H-dev items and sampling seeds on all three devices. Historical A/B evaluations were collected previously, on the devices recorded in their original metadata. The probe tests this serving configuration on these items and does not establish cross-device training equivalence. The default seven-day start cutoff is an operational choice that allows headroom for the estimated 57 hours and reruns.

At 07:11 KST, C training started on all three devices. The device probe produced five calls on each device. Both non-reference devices differed from the reference in raw response bytes. The test includes separate vLLM server starts, so it cannot isolate hardware from serving nondeterminism.

The same-GPU baseline plan reuses 70 of 180 historical A/B cells. The other 110 cells (40 CT10K, 5 H-dev and 65 E1) will be measured on the assigned GPU using the verified original adapters. The launcher schedules these measurements after the registered treatment runs. The historical A/B analysis is retained as a sensitivity analysis. The same-GPU estimates use the same contrasts, endpoints, seeds and bootstrap rules. Historical base samples used to define collapse thresholds stay fixed.
