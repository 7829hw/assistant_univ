# -*- coding: utf-8 -*-
"""thinking 켬 HF 생성 공통 부품(평가·trace 수집이 같이 쓴다).

- thor ``training.inference.HFClient``로 모델을 올리고(BF16, transformers 기본 SDPA), chat template에
  ``enable_thinking=True``를 준다. 렌더링은 학습과 같은 ``training.trainer_common.render_prompt``다.
- 응답은 생성 token을 그대로 decode한 원문(``<think>…</think>`` 포함)을 ``</think>`` 기준으로 나눠, Ollama처럼
  ``message.thinking``과 ``message.content``로 돌려준다. ``</think>``가 없으면(생성 상한) content는 비고 ``done_reason``은 length다.
- 원문과 생성 token id를 ``last``에 남겨 바이트 비교와 학습 completion 검증에 쓴다.
"""
import hashlib

MODEL = "Qwen/Qwen3-8B"
REVISION = "b968826d9c46dd6066d109eabc6255188de91218"
#: thinking을 담을 생성 상한. 측정 전에 정했고 측정 중에 바꾸지 않는다.
MAX_NEW_TOKENS = 8192
#: Qwen3 권장 thinking 표본 설정.
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20}
THINK_END = "</think>"


def split_thinking(raw):
    """원문 → (thinking, content, closed). 앞의 ``<think>``와 양끝 공백만 뗀다."""
    if THINK_END not in raw:
        body = raw.split("<think>", 1)[-1]
        return body.strip(), "", False
    head, tail = raw.split(THINK_END, 1)
    return head.split("<think>", 1)[-1].strip(), tail.strip(), True


def load_client(*, adapter=None, revision=REVISION, max_new_tokens=MAX_NEW_TOKENS):
    from training.inference import HFClient

    class ThinkingClient(HFClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.config["chat_template_kwargs"] = {"enable_thinking": True}
            self.last = None

        def generate(self, messages, *, sample=False, num_return_sequences=1, seed=None):
            import torch
            from training.trainer_common import render_prompt
            text = render_prompt(self.tokenizer, messages, self.config)
            inputs = self.tokenizer(text, return_tensors="pt", add_special_tokens=False).to(self.policy.device)
            options = dict(max_new_tokens=self.max_new_tokens, use_cache=True, pad_token_id=self.tokenizer.pad_token_id,
                           num_return_sequences=num_return_sequences)
            if sample:
                options.update(do_sample=True, **SAMPLING)
            else:
                options.update(do_sample=False)
            if seed is not None:
                torch.manual_seed(seed)
                torch.cuda.manual_seed_all(seed)
            with torch.inference_mode():
                outputs = self.policy.generate(**inputs, **options)
            prompt_len = inputs.input_ids.shape[1]
            stop_ids = {self.tokenizer.eos_token_id, self.tokenizer.convert_tokens_to_ids("<|im_end|>"),
                        self.tokenizer.pad_token_id}
            results = []
            for row in outputs:
                ids = [int(i) for i in row[prompt_len:]]
                while ids and ids[-1] == self.tokenizer.pad_token_id and len(ids) > 1 and ids[-2] in stop_ids:
                    ids.pop()   # 여러 표본을 함께 생성할 때 끝난 뒤 채운 pad
                ended = bool(ids) and ids[-1] in stop_ids
                raw = self.tokenizer.decode(ids, skip_special_tokens=True)
                thinking, content, closed = split_thinking(raw)
                results.append({"raw_text": raw, "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                                "generated_ids": ids, "thinking": thinking, "content": content,
                                "think_closed": closed, "prompt_tokens": int(prompt_len), "generated_tokens": len(ids),
                                "done_reason": "stop" if ended else "length"})
            return results

        def chat(self, messages, tools=None, **kwargs):
            result = self.generate(messages)[0]
            self.last = result
            if hasattr(self, "log"):
                self.log.append({k: result[k] for k in ("raw_sha256", "generated_tokens", "done_reason", "think_closed")})
            return {"message": {"content": result["content"], "thinking": result["thinking"]},
                    "prompt_eval_count": result["prompt_tokens"], "eval_count": result["generated_tokens"],
                    "done_reason": result["done_reason"]}

    return ThinkingClient(MODEL, adapter=adapter, revision=revision, max_new_tokens=max_new_tokens, seed=42)
