# 평가셋 이름 → 정답 파일 (grounding_v4와 같은 7개 셋)
declare -A GOLD=(
  [at]=evaluation/grounding_v4/answer_target_questions.yaml
  [contrast]=evaluation/grounding_v2/contrast_questions.yaml
  [dev]=evaluation/vendor100/gold.yaml
  [indepv2]=evaluation/grounding_v2/independent_questions.yaml
  [indepv3]=evaluation/grounding_v2/independent_v3_questions.yaml
  [indepv4]=evaluation/grounding_v3/independent_v4_questions.yaml
  [old44]=evaluation/grounding_v1/holdout_questions.yaml
)
SETS="at contrast dev indepv2 indepv3 indepv4 old44"
