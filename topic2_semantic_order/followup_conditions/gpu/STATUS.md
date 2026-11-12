# GPU execution status

Read-only host check on workstation4, 2026-11-13 KST. All three GPUs reported 15 MiB used / 49,140 MiB and the compute-app query returned no rows. The default physical GPU `GPU-48f798cc-9437-50ac-d604-448bbad7b311` was index 2. The policy spare `GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21` was not present. Docker listed no `ollama` container and `localhost:11434/api/ps` returned connection refused. No process or container was changed. No CUDA context was created for a follow-up job. This observation is not a reservation and must be refreshed before an approved run.

No new task-specific GPU allocation, runtime limit, or new-job cutoff was confirmed. Historical decision 264/job manifests and subsequent retraining allocations apply to their original runs. [Phase 1](preview_phase1.json) and [phase 2](preview_phase2.json) previews validate only manifest structure, estimates and CPU gates. Training, serving and evaluation were not started. Coverage requires separate human data approval.

## Three-GPU allocation, 2026-11-13 KST

The user approved proceeding and using all three workstation4 GPUs. Run phases 1 and 2 in the registered order. One GPU owns each order seed and runs its new arms serially. The five-item device comparison uses the same existing B-o2026113 adapter, H-dev items and sampling seeds on all three devices. Historical A/B evaluations were collected previously, on the devices recorded in their original metadata. The probe tests this serving configuration on these items and does not establish cross-device training equivalence. The default seven-day start cutoff is an operational choice that allows headroom for the estimated 57 hours and reruns.
