#!/usr/bin/env bash
# pilot_004 작업 3: 데이터 만들기 → 검사(dry-run, tokenizer-check, 출처별 손실 token, 평가 셋 겹침) → 커밋. 하나라도 실패하면 멈춘다.
set -u
cd /home/hwkim/assistant_univ
D=sft_dpo_inventory/pilot_004/data
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
die() { echo "STOP: $1" | tee -a $D/checks.log; exit 1; }
"$PY" $D/build_pilot004.py > $D/build.log 2>&1 || die "build failed"
: > $D/checks.log
for stage in sft dpo; do
  for flag in --dry-run --tokenizer-check; do
    echo "## $stage $flag" >> $D/checks.log
    CUDA_VISIBLE_DEVICES="" "$PY" -m training.train_$stage --config training/configs/qwen3_8b_t2pc_thinking_pilot004_$stage.yaml $flag >> $D/checks.log 2>&1
    rc=$?; echo "exit=$rc" >> $D/checks.log; [ $rc -eq 0 ] || die "$stage $flag failed"
  done
done
"$PY" $D/check_loss_tokens.py > $D/check_loss_tokens.log 2>&1 || die "loss token check failed"
"$PY" $D/check_overlap.py > $D/check_overlap.log 2>&1 || die "overlap check failed"
echo "all checks passed" >> $D/checks.log
git add $D training/data/build_thinking.py training/configs/qwen3_8b_t2pc_thinking_pilot004_sft.yaml training/configs/qwen3_8b_t2pc_thinking_pilot004_dpo.yaml training/generated/thinking_pilot004_t2pc
git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "data(pilot_004): thinking_pilot004_t2pc(결정 86 출처별 손실, 결정 88·92 유형 상한, 결정 98 실차 8b 표본), 검사 통과

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed"
git push -q origin geoflow/sft-dpo-t2pc || echo "push rejected"
echo done
