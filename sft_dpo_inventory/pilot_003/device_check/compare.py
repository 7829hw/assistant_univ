# -*- coding: utf-8 -*-
"""결정 83(Y) 장치 일치 확인 결과 비교. 모델 호출 없음.

    python sft_dpo_inventory/pilot_003/device_check/compare.py

GPU 0·1·2의 호출별 원문 sha256(``gpu{g}.json``의 ``hf_calls[].raw_sha256``)과 생성 token 수를 기준 GPU 3과 바이트 단위로 비교한다.
출력: ``compare.json``(GPU별 일치 여부, 다른 호출 목록). 원문은 저장소 밖(ignore 경로)에 있다.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def calls(g):
    d = json.loads((HERE / f"gpu{g}.json").read_text(encoding="utf-8"))
    out = {}
    for r in d["rows"]:
        for n, c in enumerate(r.get("hf_calls") or []):
            out[(r["id"], n)] = (c["raw_sha256"], c["generated_tokens"])
    return out, d["meta"]["hf"].get("device_uuid")


def main():
    ref, ref_uuid = calls(3)
    result = {"reference": {"gpu": 3, "uuid": ref_uuid, "calls": len(ref)}, "gpus": {}}
    for g in (0, 1, 2):
        got, uuid = calls(g)
        diff = sorted(f"{k[0]}#{k[1]}" for k in set(ref) | set(got) if ref.get(k) != got.get(k))
        result["gpus"][g] = {"uuid": uuid, "calls": len(got), "byte_identical": not diff, "different_calls": diff}
    result["all_identical"] = all(v["byte_identical"] for v in result["gpus"].values())
    result["rule"] = ("모두 같음: 표본을 GPU에 자유롭게 나눈다" if result["all_identical"] else
                      "다른 GPU 있음: 한 셀의 모든 표본을 한 GPU에서, 쌍 비교의 두 셀은 같은 GPU에서 잰다")
    (HERE / "compare.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
