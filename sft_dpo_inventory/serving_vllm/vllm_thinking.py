# -*- coding: utf-8 -*-
"""vLLM(OpenAI 호환 서버) thinking 켬 client. ``thinking_prep_001/hf_thinking.py``와 같은 인터페이스다(결정 89).

- 렌더링은 HF 평가와 같은 ``training.trainer_common.render_prompt``(chat template, ``enable_thinking=True``)이고,
  렌더링한 문자열을 같은 tokenizer로 token id열로 바꿔 ``/v1/completions``의 ``prompt``에 **id열 그대로** 넣는다.
  서버 쪽 chat template·tokenize를 거치지 않으므로 입력 token이 HF 경로와 같다(응답의 ``prompt_token_ids``로 확인해 기록한다).
- 생성 token id(``return_token_ids``)를 같은 tokenizer로 ``skip_special_tokens=True`` decode해 원문을 만든다(HF와 같은 처리).
  끝 token이 정지 token이면 done_reason=stop, 아니면 length.
- sampling: ``sampling_call``(``{"seed", "params"}``)이 있으면 그 값을 요청에 그대로 넣고, presence·frequency penalty 0을 명시한다.
  요청 본문과 응답의 finish_reason을 ``last``에 남긴다.
- 이 파일은 ``SEMANTIC_CODE`` 밖이다(평가 도구).
"""
import hashlib
import json
import time
import urllib.request

import hf_thinking as H

THINK_END = H.THINK_END


class VLLMThinkingClient:
    def __init__(self, base_url, served_model, *, max_new_tokens=H.MAX_NEW_TOKENS, timeout=3600):
        from transformers import AutoTokenizer
        self.base_url = base_url.rstrip("/")
        self.served_model = served_model
        self.max_new_tokens = max_new_tokens
        self.timeout = timeout
        self.tokenizer = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
        self.config = {"chat_template_kwargs": {"enable_thinking": True}}
        self.stop_ids = {self.tokenizer.eos_token_id, self.tokenizer.convert_tokens_to_ids("<|im_end|>"),
                         self.tokenizer.pad_token_id}
        self.last = None
        self.log = []
        self.sampling_call = None
        self.model = served_model

    def prompt_ids(self, messages):
        from training.trainer_common import render_prompt
        text = render_prompt(self.tokenizer, messages, self.config)
        return self.tokenizer(text, add_special_tokens=False)["input_ids"]

    def _post(self, path, body):
        req = urllib.request.Request(self.base_url + path, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def generate(self, messages, *, sample=False, seed=None, sampling=None):
        ids = self.prompt_ids(messages)
        body = {"model": self.served_model, "prompt": ids, "max_tokens": self.max_new_tokens, "return_token_ids": True,
                "skip_special_tokens": True, "presence_penalty": 0.0, "frequency_penalty": 0.0, "n": 1}
        if sample:
            body.update(sampling or H.SAMPLING)
            if seed is not None:
                body["seed"] = int(seed)
        else:
            body.update(temperature=0.0)
        started = time.perf_counter()
        out = self._post("/v1/completions", body)
        seconds = time.perf_counter() - started
        choice = out["choices"][0]
        gen = [int(i) for i in choice.get("token_ids") or []]
        sent_back = choice.get("prompt_token_ids") or out.get("prompt_token_ids")
        ended = bool(gen) and gen[-1] in self.stop_ids
        raw = self.tokenizer.decode(gen, skip_special_tokens=True)
        thinking, content, closed = H.split_thinking(raw)
        return {"raw_text": raw, "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(), "generated_ids": gen,
                "thinking": thinking, "content": content, "think_closed": closed, "prompt_tokens": len(ids),
                "generated_tokens": len(gen), "done_reason": "stop" if ended else "length",
                "finish_reason": choice.get("finish_reason"), "server_seconds": round(seconds, 3),
                "prompt_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
                "prompt_ids_echo_equal": None if sent_back is None else [int(i) for i in sent_back] == ids,
                "request": {k: v for k, v in body.items() if k != "prompt"}}

    def chat(self, messages, tools=None, **kwargs):
        call = self.sampling_call
        result = (self.generate(messages, sample=True, seed=call["seed"], sampling=call["params"]) if call
                  else self.generate(messages))
        self.last = result
        entry = {k: result[k] for k in ("raw_sha256", "generated_tokens", "done_reason", "think_closed", "finish_reason",
                                         "server_seconds", "prompt_tokens", "prompt_ids_sha256", "prompt_ids_echo_equal")}
        if call:
            entry["sampling_seed"] = call["seed"]
        self.log.append(entry)
        response = {"message": {"content": result["content"], "thinking": result["thinking"]},
                    "prompt_eval_count": result["prompt_tokens"], "eval_count": result["generated_tokens"],
                    "done_reason": result["done_reason"]}
        if call:
            response["sampling_seed"] = call["seed"]
        return response
