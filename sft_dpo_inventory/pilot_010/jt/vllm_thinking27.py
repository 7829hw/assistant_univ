# -*- coding: utf-8 -*-
"""pilot_010 JT(결정 271, PLAN_JT) 교사 참고 측정 client: ``serving_vllm/vllm_thinking.py``의 ``VLLMThinkingClient``(그대로 둠)를 상속한다.
바꾼 것은 ``__init__`` 하나다: tokenizer·chat template를 Qwen/Qwen3.8-27B(revision 37561816…, 저장소 밖 로컬 사본)의 것으로,
정지 token을 그 tokenizer의 ``eos``(``<|im_end|>``)·``<|im_end|>``·``pad``(``<|endoftext|>``)로 둔다(학생 client와 같은 규칙).
렌더링(``training.trainer_common.render_prompt``, ``enable_thinking=True``만 줌 → 그 밖 template 인자는 기본값), id열을 ``/v1/completions``에 그대로 넣기,
``skip_special_tokens=True`` decode, ``</think>`` 기준 분리(``hf_thinking.split_thinking``), 요청 본문·기록 형식은 부모 클래스 그대로다.
- 27B template는 thinking 켬·``reasoning_effort`` 기본(xhigh)일 때 system 앞에 effort 문장을 넣고 생성 프롬프트를 ``<think>\\n``으로 연다(PLAN_JT 2절, 사전 고정).
"""
import hashlib
from pathlib import Path

import vllm_thinking as VT

MODEL27 = "Qwen/Qwen3.8-27B"
REVISION27 = "37561816e66b5b9153b1b64c10968c18c1e6f4a0"
LOCAL27 = "/data/hwkim/sftdpo_work/pilot_010_jt/model/Qwen3.8-27B"


class VLLMThinkingClient27(VT.VLLMThinkingClient):
    def __init__(self, base_url, served_model, *, max_new_tokens=VT.H.MAX_NEW_TOKENS, timeout=3600):
        from transformers import AutoTokenizer
        self.base_url = base_url.rstrip("/")
        self.served_model = served_model
        self.max_new_tokens = max_new_tokens
        self.timeout = timeout
        self.tokenizer = AutoTokenizer.from_pretrained(LOCAL27)
        self.config = {"chat_template_kwargs": {"enable_thinking": True}}
        self.stop_ids = {self.tokenizer.eos_token_id, self.tokenizer.convert_tokens_to_ids("<|im_end|>"),
                         self.tokenizer.pad_token_id}
        self.last = None
        self.log = []
        self.sampling_call = None
        self.model = served_model
        tpl = Path(LOCAL27) / "chat_template.jinja"
        self.template_sha256 = hashlib.sha256(tpl.read_bytes()).hexdigest() if tpl.exists() else None
