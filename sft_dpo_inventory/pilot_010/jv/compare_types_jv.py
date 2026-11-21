# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273): Q4 GGUF의 텐서 이름·모양·타입을 공식 qwen3:8b blob(``a3de86cd…``, 읽기만)과 대조한다. CPU, 모델 호출 없음.
``quant_recipe/compare_types.py``(바꾸지 않음, 결정 75)의 같은 비교를 파일 하나씩 하도록 옮긴 것(그 스크립트는 경로가 고정이라 그대로 쓸 수 없음).

    runtime/envs/llamacpp/bin/python sft_dpo_inventory/pilot_010/jv/compare_types_jv.py FILE.gguf
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import models_jv as M  # noqa: E402

LLAMA_PY = "/data/hwkim/sftdpo_work/runtime/envs/llamacpp/bin/python"


def tensors(path):
    from gguf import GGUFReader
    reader = GGUFReader(path)
    return {t.name: {"type": t.tensor_type.name, "shape": [int(x) for x in t.shape]} for t in reader.tensors}


def _compare_here(path):
    off, got = tensors(M.OFFICIAL_QWEN3_8B_BLOB), tensors(path)
    names = sorted(set(off) | set(got))
    same = sum(1 for n in names if n in off and n in got and off[n]["type"] == got[n]["type"])
    diff = [n for n in names if n in off and n in got and off[n]["type"] != got[n]["type"]]
    shape = sum(1 for n in names if n in off and n in got and off[n]["shape"] != got[n]["shape"])
    return {"file": path, "official_blob": M.OFFICIAL_QWEN3_8B_BLOB, "official_tensors": len(off), "tensors": len(got),
            "missing_in_file": sorted(set(off) - set(got)), "extra_in_file": sorted(set(got) - set(off)),
            "same_type": same, "diff_type": len(diff), "diff_examples": diff[:10], "shape_diff": shape,
            "type_counts": dict(sorted(Counter(v["type"] for v in got.values()).items())),
            "official_type_counts": dict(sorted(Counter(v["type"] for v in off.values()).items()))}


def compare(path):
    """llamacpp 환경(gguf-py)에서 비교해 dict로 돌려준다(호출하는 쪽 환경과 무관)."""
    r = subprocess.run([LLAMA_PY, str(Path(__file__).resolve()), path], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-2000:])
    return json.loads(r.stdout)


if __name__ == "__main__":
    print(json.dumps(_compare_here(sys.argv[1]), ensure_ascii=False))
