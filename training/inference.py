"""Hugging Face client adapter for the existing GeoFlowPlanner chat protocol."""
import json
from pathlib import Path

from training.data.common import production_prompt
from training.trainer_common import model_for, render_prompt, tokenizer_for


def check_checkpoint_prompt(path):
    import hashlib
    provenance = Path(path) / "training_provenance.json"
    if not provenance.exists():
        return None
    info = json.loads(provenance.read_text(encoding="utf-8"))
    if info["prompt_hash"] != hashlib.sha256(production_prompt().encode()).hexdigest():
        raise ValueError("Checkpoint production prompt drift; evaluate an explicitly matched prompt/version")
    return info


class HFClient:
    def __init__(self, model, *, adapter=None, revision=None, load_in_4bit=False, max_new_tokens=1024, seed=42):
        import torch
        from transformers import set_seed
        set_seed(seed)
        self.model = model + (f"+{adapter}" if adapter else "")
        info = check_checkpoint_prompt(adapter or model)
        self.config = {"model": {"name_or_path": model, "load_in_4bit": load_in_4bit,
                                  "revision": revision or (info or {}).get("config", {}).get("model", {}).get("revision", "main")},
                       "training": {"bf16": torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
                                    "gradient_checkpointing": False},
                       "chat_template_kwargs": (info or {}).get("config", {}).get("chat_template_kwargs", {"enable_thinking": False})}
        self.tokenizer = tokenizer_for(self.config)
        self.policy = model_for(self.config)
        if adapter:
            from peft import PeftModel
            self.policy = PeftModel.from_pretrained(self.policy, adapter)
        if not load_in_4bit:
            self.policy.to("cuda" if torch.cuda.is_available() else "cpu")
        self.policy.eval()
        self.max_new_tokens = max_new_tokens

    def chat(self, messages, tools=None, **kwargs):
        import torch
        text = render_prompt(self.tokenizer, messages, self.config)
        inputs = self.tokenizer(text, return_tensors="pt", add_special_tokens=False).to(self.policy.device)
        with torch.inference_mode():
            outputs = self.policy.generate(**inputs, max_new_tokens=self.max_new_tokens,
                                           do_sample=False, use_cache=True,
                                           pad_token_id=self.tokenizer.pad_token_id)
        content = self.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        return {"message": {"content": content}}
