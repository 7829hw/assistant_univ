# R70 loss mask 검증

2026-10-13. 학습 전. `loss_mask_audit.py` → `loss_mask_audit.json`, `loss_mask_examples.txt`.

## 1. 방법

- 학습 코드(`training.train_sft.train`)와 같은 순서로 SFTTrainer를 만든다.
  - config → `load_records` → `render_records` → SFTConfig(같은 수정: completion_only_loss, packing 끔) → SFTTrainer
- 70개 레코드를 `trainer.data_collator`에 넣어 실제 `labels` tensor를 얻는다.
- 모델만 작은 무작위 Qwen3(같은 tokenizer, CPU)로 바꿨다. dataset tokenize와 label 생성은 모델과 무관한 TRL 코드다.
- collator의 `input_ids`가 렌더링 문자열(prompt + completion)을 한 번에 tokenize한 결과와 같은지 확인했다(70/70 같음).
  - 그 다음 offset으로 token마다 영역을 정했다: system_user(assistant 머리 포함), think_open, thinking, think_close(`</think>`와 뒤 줄바꿈), json, eos.
- `label == -100`이면 MASK, 아니면 LOSS로 셌다.

## 2. 결과(70개 레코드 합)

| 영역 | R70-json(json_only) | R70-full(full_response) |
|---|---|---|
| system_user | MASK 485,109 | MASK 485,109 |
| think_open(`<think>`) | MASK 70 | **LOSS 70** |
| thinking 본문 | MASK 64,245 | **LOSS 64,245** |
| think_close(`</think>` + `\n\n`) | MASK 140 | **LOSS 140** |
| JSON | LOSS 6,265 | LOSS 6,265 |
| EOS(`<|im_end|>`) | LOSS 70 | LOSS 70 |

- 두 arm 모두 기대와 레코드 70/70이 일치한다(`ok: true`, 불일치 0).
- 두 arm의 `input_ids`는 문항마다 같다(`identical_input_ids_both_arms: true`). 차이는 label뿐이다.
- `full_response`의 thinking은 실제로 supervised token이다(prompt 쪽이 아니다).
  - 렌더링에서 prompt는 `<|im_start|>assistant\n`에서 끝나고, `<think>`부터 completion이다.
- `json_only`에서는 thinking이 prompt 쪽에 붙는다. 그래서 assistant의 첫 token `<think>`가 MASK다.
  - p0_sft_001(json_only)에서 모델이 `<think>`를 낼 이유를 학습하지 못했다는 설명과 맞는다.
  - 답만 있는 레코드는 첫 token `{`가 LOSS였다.

## 3. 예제(`loss_mask_examples.txt`, 3개씩)

ann-d983889cf8c496178106, 영역이 바뀌는 token만 적는다:

```
R70-json                                   R70-full
[    0] system_user  MASK "<|im_start|>"   [    0] system_user  MASK "<|im_start|>"
[ 6918] think_open   MASK "<think>"        [ 6918] think_open   LOSS "<think>"
[ 6919] thinking     MASK "\n"             [ 6919] thinking     LOSS "\n"
[ 7978] think_close  MASK "</think>"       [ 7978] think_close  LOSS "</think>"
[ 7980] json         LOSS "{\""            [ 7980] json         LOSS "{\""
[ 8062] eos          LOSS "<|im_end|>"     [ 8062] eos          LOSS "<|im_end|>"
```

- `<think>`와 `</think>`는 Qwen3 tokenizer에서 각각 token 하나다.
- 이 검증을 통과했으므로 trainer를 고치지 않고 학습한다.
