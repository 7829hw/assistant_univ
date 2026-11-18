# -*- coding: utf-8 -*-
"""pilot_010 JQ 표(결정 269) — ``jq_ensemble.json``(A)·``jq_v8new.json``(B, 있으면)에서 그대로 만든다. 새 수치를 만들지 않는다.

    python3 sft_dpo_inventory/pilot_010/results/tables_jq.py > sft_dpo_inventory/pilot_010/results/jq_tables.md
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = json.loads((HERE / "jq_ensemble.json").read_text(encoding="utf-8"))
BP = HERE / "jq_v8new.json"
B = json.loads(BP.read_text(encoding="utf-8")) if BP.exists() else None
M = ("correct_refusal", "over_refusal_100", "over_refusal_contrast25", "accuracy_100", "hfinal_accuracy", "hfinal_over_refusal")
H = "| | PF2 올바른 거부(50) | PF2 과잉 거부(답하는 100) | PF2 과잉 거부(근접 25) | PF2 정답률(100) | H-final 정답률(3,000) | H-final 과잉 거부율 |"
SEP = "|---|---|---|---|---|---|---|"
N = A["names"]
ARMS = ("B2F", "P9", "V4", "V8")
CATS = ("correct", "refused_M", "refused_P", "refused_C", "truncated", "U", "silent", "other_fail")
CATN = {"correct": "정답", "refused_M": "거부 M", "refused_P": "거부 P", "refused_C": "거부 C", "truncated": "잘림", "U": "U", "silent": "조용한 오답", "other_fail": "그 밖 실패"}


def e(x):
    return f"{x['mean_pct']:.2f} [{x['ci95_pct'][0]:.2f}, {x['ci95_pct'][1]:.2f}]"


def d(x):
    return f"{x['diff_pp']:+.2f} [{x['ci95_pp'][0]:+.2f}, {x['ci95_pp'][1]:+.2f}]"


def r(s):
    return f"{s['mean']:.2f} [{s['min']:.2f}–{s['max']:.2f}]"


def t1():
    out = ["**표 1 — 구성별 단일 모델 seed 평균 대 seed 앙상블(판정 뒤 추가(사후), PF2·H-final 두 번째 사용)**. 칸: 값 [95% CI]. 단일 = U1 bootstrap(문항+seed), 앙상블 = 문항 bootstrap(seed 집합 고정). 10,000회.", "", H, SEP]
    out.append("| base(k=8 / 2회차) | " + " | ".join(e(A["base"]["metrics"][m]) for m in M) + " |")
    for a in ARMS:
        c = A["configs"][a]
        out.append(f"| {N[a]} 단일 평균(n={c['n']}) | " + " | ".join(e(c["single_mean"][m]) for m in M) + " |")
        out.append(f"| **{N[a]} 앙상블(n={c['n']})** | " + " | ".join(e(c["ensemble"][m]) for m in M) + " |")
    return out


def t1b():
    out = ["", "**표 1b — H-final 앙상블 결과 분해·template_group 붕괴(판정 뒤 추가(사후))**. 분해 = 표본마다 한 범주(정답 → 거부 M·P·C → 잘림 → U → 조용한 오답 → 그 밖 실패), %. "
           "붕괴 = 30문항 이상 그룹 59개 중 base 그룹 정답률(두 회차 평균)보다 20%p·30%p 넘게 낮은 그룹 수. 단일은 seed 평균.", "",
           "| 구성 | " + " | ".join(CATN[c] for c in CATS) + " | 붕괴 −20%p | 붕괴 −30%p |", "|---|" + "---|" * (len(CATS) + 2)]
    for a in ARMS:
        c = A["configs"][a]
        s, en = c["hfinal_single"], c["hfinal_ensemble"]
        out.append(f"| {N[a]} 단일 | " + " | ".join(f"{s['decomposition_seed_mean'][k]:.2f}" for k in CATS)
                   + f" | {s['group_collapse_mean']['below_base_20pp']:.1f} | {s['group_collapse_mean']['below_base_30pp']:.1f} |")
        out.append(f"| {N[a]} 앙상블 | " + " | ".join(f"{en['decomposition'][k]:.2f}" for k in CATS)
                   + f" | {en['group_collapse']['below_base_20pp']} | {en['group_collapse']['below_base_30pp']} |")
    types = list(A["configs"]["B2F"]["hfinal_ensemble"]["accuracy_by_tool_type"])
    out += ["", "*H-final 도구 유형별 정답률(%, 단일 seed 평균 → 앙상블)*", "", "| 도구 유형 | 문항 | " + " | ".join(N[a] for a in ARMS) + " |", "|---|---|" + "---|" * len(ARMS)]
    for t in types:
        n = A["configs"]["B2F"]["hfinal_ensemble"]["accuracy_by_tool_type"][t]["items"]
        cells = [f"{A['configs'][a]['hfinal_single']['accuracy_by_tool_type_seed_mean'][t]['pct']:.2f} → {A['configs'][a]['hfinal_ensemble']['accuracy_by_tool_type'][t]['pct']:.2f}" for a in ARMS]
        out.append(f"| {t} | {n} | " + " | ".join(cells) + " |")
    out += ["", "*PF2 앙상블 형별 올바른 거부(%, M 34·P 10·C 6)*", "", "| 구성 | M | P | C |", "|---|---|---|---|"]
    for a in ARMS:
        f = A["configs"][a]["pf2_ensemble"]["correct_refusal_by_form"]
        out.append(f"| {N[a]} 앙상블 | " + " | ".join(f"{f[k]['pct']:.2f}" for k in ("M", "P", "C")) + " |")
    return out


def t2():
    out = ["", "**표 2 — 앙상블 차이(%p, 판정 뒤 추가(사후))**. 칸: 차 [95% CI]. 앙상블 쪽은 문항만, 단일 평균 쪽은 문항+seed 재추출(U1), 문항 번호 공유, 통계량마다 default_rng(20261109).", "",
           H.replace("| |", "| 비교 |"), SEP]
    for a in ARMS:
        c = A["configs"][a]
        out.append(f"| {N[a]} 앙상블 − {N[a]} 단일 | " + " | ".join(d(c["ensemble_minus_own_single"][m]) for m in M) + " |")
        if a != "B2F":  # SFT는 자기 단일과 같은 행
            out.append(f"| {N[a]} 앙상블 − SFT 단일 | " + " | ".join(d(c["ensemble_minus_sft_single"][m]) for m in M) + " |")
        if "ensemble_minus_sft_ensemble" in c:
            out.append(f"| {N[a]} 앙상블 − SFT 앙상블 | " + " | ".join(d(c["ensemble_minus_sft_ensemble"][m]) for m in M) + " |")
        out.append(f"| {N[a]} 앙상블 − base | " + " | ".join(d(c["ensemble_minus_base"][m]) for m in M) + " |")
    return out


def t3():
    out = ["", "**표 3 — n=3 앙상블(판정 뒤 추가(사후))**. seed 5개 구성은 3개 조합 10가지의 점추정 평균 [최소–최대]. RR+NM8은 seed 3개라 조합 하나(= 전체 앙상블).", "",
           H.replace("| |", "| 구성 |"), SEP]
    for a in ARMS:
        c = A["combos3"][a]
        out.append(f"| {N[a]} n=3 ({c['combos']}조합) | " + " | ".join(r(c["summary"][m]) for m in M) + " |")
    return out


def t4():
    out = ["", "**표 4 — CT10K·H-dev 재현(RR+NM4 = V4 6 seed, 판정 뒤 추가(사후))**. 정답률 = `category == match`, 과잉 거부 = 거부(sample_rows). 칸: 값 [95% CI] 또는 조합 평균 [최소–최대](3개 조합 20가지).", "",
           "| 셋 | 문항 | base | V4 단일 평균(6) | V4 앙상블(6) | n=3 조합 | 앙상블 − 단일 | 앙상블 − base | 단일 − base |", "|---|---|---|---|---|---|---|---|---|"]
    for name, b in A["broad"].items():
        for f, lab in (("accuracy", "정답률"), ("over_refusal", "과잉 거부")):
            out.append(f"| {name} {lab} | {b['items']} | {e(b['base'][f])} | {e(b['single_mean'][f])} | {e(b['ensemble'][f])} | {r(b['combos3']['summary'][f])} | "
                       f"{d(b['ensemble_minus_single'][f])} | {d(b['ensemble_minus_base'][f])} | {d(b['single_minus_base'][f])} |")
    return out


def t5():
    out = ["", "**표 5 — PF2 단일 모델 안 거부 재확인(판정 뒤 추가(사후))**. 표본 (1,2)·(3,4) 짝: 첫 표본이 거부면 둘째를 보고 둘 다 거부일 때만 거부. 칸: seed 평균 [U1 CI]. "
           "‘짝 차이’는 같은 seed 안 재확인 − 단일(4표본)의 seed 평균(계획에 없던 추가 표시).", "",
           "| 구성 | 규칙 | PF2 올바른 거부 | 과잉 거부 100 | 과잉 거부 근접 25 | PF2 정답률 | 문항당 호출 | wall p50 | wall p95 |", "|---|---|---|---|---|---|---|---|---|"]
    for a in ARMS:
        c = A["recheck"][a]
        for tag, lab in (("single", "단일"), ("recheck", "재확인")):
            out.append(f"| {N[a]} | {lab} | " + " | ".join(e(c[tag][m]) for m in M[:4]) + f" | {c['cost'][tag]['llm_calls_per_item']:.3f} | {c['cost'][tag]['wall_p50_s']:.1f} | {c['cost'][tag]['wall_p95_s']:.1f} |")
        out.append(f"| {N[a]} | 짝 차이 | " + " | ".join(f"{c['paired_recheck_minus_single_extra'][m]['mean_pct']:+.2f} [{c['paired_recheck_minus_single_extra'][m]['ci95_pct'][0]:+.2f}, {c['paired_recheck_minus_single_extra'][m]['ci95_pct'][1]:+.2f}]" for m in M[:4]) + " | | | |")
    return out


def t6():
    if B is None:
        return ["", "**표 6 — RR+NM8 새 seed 대 기존 seed**: B 측정이 끝난 뒤 채운다."]
    S = B["single"]
    out = ["", "**표 6a — RR+NM8 새 4 seed 대 기존 3 seed(판정 뒤 추가(사후), PF2·H-final 두 번째 사용)**. 칸: seed 평균 [U1 CI]; seed별은 아래.", "", H.replace("| |", "| arm |"), SEP]
    for k, lab in (("V8old", "RR+NM8 기존 3"), ("V8new", "RR+NM8 새 4"), ("V8all", "RR+NM8 7")):
        out.append(f"| {lab} | " + " | ".join(e(S[k][m]) for m in M) + " |")
    out.append(f"| RR+NM8 새 4 앙상블 | " + " | ".join(e(B["ensembles"]["V8new"]["ensemble"][m]) for m in M) + " |")
    out.append(f"| RR+NM8 7 앙상블 | " + " | ".join(e(B["ensembles"]["V8all"]["ensemble"][m]) for m in M) + " |")
    out += ["", "*seed별(%)*", "", H.replace("| |", "| seed |"), SEP]
    for s in B["all7_seeds"]:
        tag = "새" if s in B["new_seeds"] else "기존"
        out.append(f"| {s}({tag}) | " + " | ".join(f"{B['per_seed'][s][m]:.2f}" for m in M) + " |")
    out += ["", "**표 6b — 차이(%p)**. 칸: 차 [95% CI].", "", H.replace("| |", "| 비교 |"), SEP]
    lab = {"V8new": "RR+NM8 새 4", "V8all": "RR+NM8 7"}
    for k, c in B["comparisons"].items():
        x, y = k.split("-", 1)
        out.append(f"| {lab.get(x, x)} − {N.get(y, 'RR+NM8 기존 3' if y == 'V8old' else y)} | " + " | ".join(d(c[m]) for m in M) + " |")
    for k in ("V8new", "V8all"):
        c = B["ensembles"][k]
        for kk, l2 in (("ensemble_minus_own_single", f"{lab[k]} 단일"), ("ensemble_minus_sft_single", "SFT 단일"), ("ensemble_minus_sft_ensemble", "SFT 앙상블"), ("ensemble_minus_base", "base")):
            out.append(f"| {lab[k]} 앙상블 − {l2} | " + " | ".join(d(c[kk][m]) for m in M) + " |")
    return out


def t7():
    out = ["", "**표 7 — 비용(판정 뒤 추가(사후))**. 문항당 LLM 호출 = 모델별 호출의 합(단일은 모델 평균). wall = 문항별 started→finished(초); 앙상블은 모델별 wall의 최댓값(병렬 호출 가정). "
           "p50·p95는 모든 문항×표본에서. 측정 때 동시 요청 수(PF2 8, H-final 32)의 영향을 받은 값이며 실제 병렬 배치 시간이 아니다.", "",
           "| 구성 | 셋 | 단일 호출 | 앙상블 호출 | 단일 wall p50 | 앙상블 wall p50 | 단일 wall p95 | 앙상블 wall p95 |", "|---|---|---|---|---|---|---|---|"]
    rows = [(N[a], A["configs"][a]["cost"]) for a in ARMS]
    if B is not None:
        rows += [("RR+NM8 새 4", B["ensembles"]["V8new"]["cost"]), ("RR+NM8 7", B["ensembles"]["V8all"]["cost"])]
    for name, c in rows:
        for st, lab in (("pf2", "PF2"), ("hfinal", "H-final")):
            s, en = c["single_mean"][st], c["ensemble"][st]
            out.append(f"| {name} | {lab} | {s['llm_calls_per_item']:.3f} | {en['llm_calls_per_item']:.3f} | {s['wall_p50_s']:.1f} | {en['wall_p50_s']:.1f} | {s['wall_p95_s']:.1f} | {en['wall_p95_s']:.1f} |")
    b = A["base"]["cost"]
    out.append(f"| base | PF2 | {b['pf2']['llm_calls_per_item']:.3f} | — | {b['pf2']['wall_p50_s']:.1f} | — | {b['pf2']['wall_p95_s']:.1f} | — |")
    out.append(f"| base | H-final | {b['hfinal']['llm_calls_per_item']:.3f} | — | {b['hfinal']['wall_p50_s']:.1f} | — | {b['hfinal']['wall_p95_s']:.1f} | — |")
    return out


def main():
    lines = t1() + t1b() + t2() + t3() + t4() + t5() + t6() + t7()
    kc = A["key_consistency"]
    lines += ["", "검사: 같은 문항·같은 정규형 키를 낸 표본들의 정답 값 불일치 — " + ", ".join(f"{N[k.split(':')[0]]} PF2 {v['pf2']['inconsistent']}/{v['pf2']['groups']} · H-final {v['hfinal']['inconsistent']}/{v['hfinal']['groups']}" for k, v in kc.items())
              + "; CT10K " + f"{A['broad']['CT10K']['key_consistency']['inconsistent']}/{A['broad']['CT10K']['key_consistency']['groups']}"
              + ", H-dev " + f"{A['broad']['H-dev']['key_consistency']['inconsistent']}/{A['broad']['H-dev']['key_consistency']['groups']}" + "(전체 앙상블 기준)."]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
