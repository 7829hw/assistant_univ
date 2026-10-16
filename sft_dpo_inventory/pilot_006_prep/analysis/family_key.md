# family 키 분석(H3 준비, 2026-10-16)

계산: `family_key_analysis.py` → `family_key_analysis.json`(셋별 family 구조, 문장 없음), 빈 구조: `../../batch009/free_structures.py` → `free_structures.json`.

## 1. family 키가 정해지는 것

`training.annotations.inventory.family_key(payload)` = digest([**측정**(concept, subtype) 목록, **장소 od_role** 목록(LOCATION 노드), factors 가운데
**aggregation · rollup · bucket · answer(value 제외) · dimension · dimension_target · order · vicinity**]).

- 들어가지 않는 것: 질문 문장, 장소·scope 값, 날짜·시간, 택시 유형, **운행 상태(taxi_status)**, **limit**, 조건 노드.
- 그래서 "같은 측정 + 같은 끝 구조 + 같은 묶음·순위 방향"이면 장소·날짜·표현을 모두 바꿔도 같은 family다. template 키(`template_key`)는 여기에 concept·role과
  조건 factor 자리표를 더한 더 좁은 키다.

## 2. 결정 120에서 막히는 family

결정 120: selection_v2·augmentation_holdout_v1·valid98·aux_test_v1과 family가 같으면 학습 후보에서 뺀다(업체 100만·template만은 되살림).
다섯 셋(+selection_v1, 업체 100)의 family 151개 중 **143개가 넷 중 하나에 있다**(selection_v2 62, valid98 74, aux 40, holdout 37; 겹침 포함).

| 측정 | 막힌 family |
|---|---:|
| 실차 건수(trip_count) | 48 |
| 수입(revenue) | 28 |
| 가동률 | 16 |
| 운행 일수 | 11 |
| 활성 택시 대수 | 9 |
| 통행량·속도 | 각 8 |
| 요금·공차율·RPM | 5·5·4 |
| 측정 없음(scope 이름 조회) | 1 |

## 3. family를 공유하기 쉬운 구조

- **scope 이름 조회(값 없는 장소)**: 측정 없음·OD 없음·factor 없음 → family가 **하나뿐**이고 selection_v2·holdout·valid98·aux가 모두 가진다.
  어떤 문장으로 써도 결정 120에 걸린다. 게다가 scope id가 mock gazetteer에 32개뿐이라 같은 scope를 쓰면 "같은 grounding"(강한 겹침)이 된다.
- **factor가 적은 단순 측정**(장소 하나 + 측정, 집계·묶음 없음): 측정 종류마다 family가 하나라 평가 셋에 거의 다 있다.
- **수입·가동률·운행 일수 + bucket/rollup·dimension**: 업체 100·valid98에 조합이 많다(billing tool만 bucket을 받아 구조 가짓수가 적음).
- **실차 건수 + dimension_target**: 구조가 (od_role 목록 5) × (dimension 4) × (dimension_target 3) × (order 3) = 180가지로 넓다. 평가 셋이 가진 것은 48개.

## 4. batch009에서 고른 구조

- `free_structures.py`: 실차 건수 180개 구조마다 정답 호출을 만들어 family를 계산하고 현재 코드로 실행했다. 보호 넷·selection_v1에 있음 55, 현재 코드 거부 24,
  확장 family(보호 원본 vendor 형식) 21, thor 보호 family 3(겹침 포함) → **빈 구조 81개**.
- w2·w3·w4는 이 빈 구조 안에서 썼다(1차 60건은 손으로 고른 조합이라 일부가 막혔고, 2차 24건은 빈 구조에서만). w1(scope 이름 조회)은 빈 구조가 없다(3절).
- 결과는 `../../batch009/README.md` 3·4절.
