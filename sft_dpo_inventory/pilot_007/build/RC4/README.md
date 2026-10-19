# RC4(pilot_007 A2 C2 — B단계 준비, **학습에 쓰지 않음**)

`../build7rc4.py`: RC4 = RC3c + batch010 승인분(승인 corpus v3, 결정 175) + S-focus 정답 표본(결정 169·176). RC3c 레코드는 그대로 두고 더하기만 했다.

| | RC3c Full | RC4 Full | RC3c Partial | RC4 Partial |
|---|---:|---:|---:|---:|
| 질문 | 369 | 386 | 369 | 386 |
| 레코드 | 1,356 | 1,411(+55) | 1,312 | 1,368(+56) |
| 8b(`json_only`) | 1,017 | 1,072 | 980 | 1,036 |
| teacher(`full_response`) | 339 | 339 | 332 | 332 |
| teacher loss token | 49.0% | 47.9% | 61.4% | 60.3% |

- **batch010 50 중 17만 들어갔다**(들어온·나간 8, bucket ↔ dimension 대조 9). 빠짐: **유형 상한 31**(소속 20 **전부**, bucket 10 **전부**, 들어온·나간 1), 한 arm 레코드 없음 2(b010-42 Partial, b010-54 Full).
  - 유형 상한(결정 88·92, τ 0.09)은 build6rc와 같은 예외·계산을 RC3c + 새 질문 전체 위에서 했고, RC3c 질문은 빼지 않았다. 소속·bucket 30문항이 속한 칸
    "집계 있음 | dim 없음 | dt 없음"은 RC3c만으로 이미 상한을 넘는다(110 > 106) → 새 질문 자리 0. 칸별 수는 `build_summary.json` `type_cap`.
  - 결정 169의 목적(소속·bucket 약점 보강)과 결정 88·92 상한이 충돌한다. 규칙을 따랐고(지시 5절: 규칙 우선), 예외 여부는 사용자 결정(예: 결정 92처럼 batch010을 상한에서 면제).
- S-focus: Full 5문항에 8b 레코드 +8(질문당 상한 4까지), Partial 1문항 +1.
- 새 8b 레코드는 build6rc 8b 경로와 같은 형식·계약·metadata, 승인 gold v3 판정(`../judge7.py`), 질문당 상한 4(`random.Random(20261016)`), 길이 ≤ 12,288.
  batch010에는 teacher trace가 없다(새 수집 없음, 결정 166).
- 검사(`../rc_checks7.py --rc RC4`): 두 arm dry-run·tokenizer-check·손실 token·마스크 audit 통과(mismatch 0). 두 arm 질문 목록 sha256 `c042c5eb…` 같음.
- 순서 공유(결정 168): `order_o43.json`·`order_o20261016.json`·`order_o7.json`(빌드 때 두 arm 질문 순서가 순서 파일과 같은지 확인). B단계 학습은 `../../train/train_b7.py`
  (`shared_order_seed`, `shared_order_file`).
- **B단계가 이 데이터를 쓰지 않을 수 있다**: A2 (a) 해석(결정 179)이 "teacher 정리가 성능을 떨어뜨렸다"이면 RC3c 계열 대신 정리 기준 재검토(선택지 (c))가 필요하다. 그 경우 RC4는 기록으로만 남는다.
