# 문항별 장소 provider 분류

`classify_providers.py`가 만든다. 장소 = subtype place인 LOCATION의 (name, region). literal scope는 조회하지 않는다.

| 출처 | id | 분류 | 평가 provider | 장소(mock / reference) | 질문 |
|---|---|---|---|---|---|
| v003_t2pc_train | ann-d983889cf8c496178106 | mock | mock | 수성구 O/X | 지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면? |
| v003_t2pc_train | ann-cc38d74754ba7eab68a8 | mock | mock | 동구 O/X | 2026년 상반기 동구 법인택시 월별 매출 평균 중 가장 큰 값은? |
| v003_t2pc_train | ann-da98b3941dfa1c7ce800 | reference_only | reference | 나래구 X/O | 2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은? |
| v003_t2pc_train | ann-77e9dacb0b34a3273630 | reference_only | reference | 나래구 X/O | 2026년 8월 나래구 개인택시 매출 평균이 가장 낮았던 주는 언제야? |
| v003_t2pc_train | ann-89f3d036b2d43dd431f0 | mock | mock | 동구 O/X | 지난달 동구 법인택시 주별 운행일수 평균 중 가장 작은 값은? |
| v003_t2pc_train | ann-aa1d7fd59c1d3d2ea97b | mock | mock | 동구 O/X | 지난달 동구 법인택시의 운행일수 평균이 가장 적었던 주는? |
| v003_t2pc_train | ann-f8d44f2cfa96200b5a95 | mock | mock | 달서구 O/X | 지난달 달서구 개인택시 주별 운행일수 평균들의 평균은? |
| v003_t2pc_train | ann-f78087861d0826ae8a7f | no_lookup | mock | — | 2026년 9월 10일 개인택시 매출 평균이 높은 시도 3곳은? |
| v003_t2pc_train | ann-e645cbc11600d7348d68 | neither | mock | 솔빛동 X/X | 2026년 9월 솔빛동에서 승차한 실차 구간을 읍면동 하차지별로 세면 건수가 많은 4곳은? |
| v003_t2pc_train | ann-9b222bf86273d158269e | neither | mock | 솔빛동 X/X | 2026년 9월 솔빛동에서 하차한 실차 구간을 읍면동 승차지별로 세면 건수가 많은 4곳은? |
| v003_t2pc_train | ann-a27c59659681a481ac2c | reference_only | reference | 가람구 X/O | 2026년 9월 가람구 소속 택시의 요금을 주마다 합산한 뒤, 주별 합계 중 가장 작은 값은? |
| v003_t2pc_train | ann-914c48dad91bc9a62ab4 | reference_only | reference | 가람구 X/O | 2026년 9월 가람구에서 기록된 도로 통행 속도의 주별 최댓값들 중 가장 작은 값은? |
| v003_t2pc_train | ann-5229788ca1f31d50214f | neither | mock | 하늘구 X/X | 2026년 7월과 8월 하늘구 소속 택시의 실차 구간별 요금을 주마다 최솟값으로 요약한 뒤, 그 주별 최솟값 |
| v003_t2pc_train | ann-b6af75820db1d74d6e15 | neither | mock | 하늘동 X/X | 2026년 7월과 8월 하늘동 안에서 관측된 도로 통행 속도의 주별 최솟값들 중 가장 큰 숫자는? |
| v003_t2pc_train | ann-b33f24e179cb6f5d84fd | no_lookup | mock | literal scope:edge:2607 | 2026년 7월과 8월 사용자가 지정한 도로 범위 scope:edge:2607 안에서 관측된 RPM을 주마다 |
| v003_t2pc_train | ann-2b2cbf79d7247f63e67a | neither | mock | 하늘구 X/X | 2026년 7월과 8월 하늘구 소속 택시의 실차 구간 요금을 주마다 평균한 뒤, 그 주별 평균 중 가장 큰  |
| v003_t2pc_train | ann-8b23b657f1c671df4b6d | neither | mock | 솔빛시 X/X; 해온시 X/X | 2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 시군구 승차지별 건수를  |
| v003_t2pc_train | ann-51491e86fd619f6c5d12 | neither | mock | 솔빛시 X/X; 해온시 X/X | 2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 시군구 하차지별 건수를  |
| v003_t2pc_train | ann-ea359d5569ef6070f9e4 | neither | mock | 하늘구 X/X | 2026년 4월부터 6월까지 하늘구 소속 법인택시의 택시·일 매출 기록을 월마다 중앙값으로 요약한 뒤, 그  |
| v003_t2pc_valid | ann-9d8392a4f8ca9ff8cfc2 | mock | mock | 중구 O/X | 2026년 상반기 중구 개인택시 운행일수 합계가 가장 많았던 달은? |
| v003_t2pc_valid | ann-0e4edbda1cb1bec194c1 | no_lookup | mock | — | 2026년 9월 읍면동 승차지별 실차 구간 건수가 적은 4개 그룹은? |
| v003_t2pc_valid | ann-0d51b49a28500bb47b0d | no_lookup | mock | — | 2026년 9월 읍면동 하차지별 실차 구간 건수가 적은 4개 그룹은? |
| v003_t2pc_valid | ann-2d254560f2214204db4b | no_lookup | mock | — | 2026년 9월 읍면동 승차지와 하차지 조합별 실차 구간 건수가 적은 4개 그룹은? |
| v003_t2pc_valid | ann-4cafcbdd3b76a67f42db | reference_only | reference | 가람구 X/O | 2026년 9월 15일 가람구에서 관측된 도로 통행의 엔진 회전수 최솟값은? |
| v003_t2pc_valid | ann-56366f545130c8b38940 | neither | mock | 하늘동 X/X | 지난달 하늘동에서 관측된 도로 통행 RPM을 주마다 중앙값으로 요약한 뒤, 그 주별 중앙값들을 동일 가중으로 |
| v003_t2pc_valid | ann-5c88583c249cfeba80ef | neither | mock | 하늘동 X/X | 2026년 7월 6일부터 8월 30일까지 하늘동에서 관측된 도로 통행 RPM을 주마다 중앙값으로 요약한 뒤, |
| v003_t2pc_valid | ann-fb7938d64ca0888db425 | neither | mock | 하늘구 X/X | 2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간별 요금 최댓값을 월마다 구하고, 그 월별 최댓값들 |
| v003_t2pc_valid | ann-f2cd5753e5bbdc07eef9 | neither | mock | 하늘동 X/X | 2026년 4월부터 6월까지 하늘동 안에서 관측된 도로 통행 속도를 월마다 산술평균하고, 그 월별 평균 중  |
| v003_t2pc_valid | ann-0d74b3178a8697d4e028 | no_lookup | mock | literal scope:edge:2608 | 2026년 4월부터 6월까지 사용자가 지정한 도로 범위 scope:edge:2608 안에서 기록된 통행 속도 |
| v003_t2pc_valid | ann-206f99f94e6aeb1e3e65 | neither | mock | 하늘동 X/X | 2026년 4월부터 6월까지 하늘동에서 관측된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을  |
| v003_t2pc_valid | ann-dbfd9d05c726d18cfb4c | neither | mock | 솔빛시 X/X; 해온시 X/X | 2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 승차지별 건수를  |
| v003_t2pc_valid | ann-dd838f31807ef8546525 | neither | mock | 솔빛시 X/X; 해온시 X/X | 2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 하차지별 건수를  |
| v003_t2pc_valid | ann-7fae41a3ed86d08a23f0 | neither | mock | 솔빛시 X/X; 해온시 X/X | 2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 승차지와 하차지의 |
| v003_t2pc_valid | ann-3584f62adae959f2eff1 | neither | mock | 하늘구 X/X | 2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간 요금 최솟값을 월마다 구했을 때, 가장 큰 숫자는 |
| v003_t2pc_valid | ann-29dcb56f51da6d6a361f | neither | mock | 하늘구 X/X | 2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간 요금 최솟값을 월마다 구했을 때, 가장 큰 최솟값 |
| batch004_candidate | b004-05 | neither | mock | 강서구(부산) X/X | 지난주 부산 강서구에서 읍면동별 택시 통행량이 가장 많은 세 곳은? |
| batch004_candidate | b004-06 | neither | mock | 강서구(부산) X/X | 지난주 부산 강서구 읍면동 가운데 택시가 가장 많이 지나간 세 곳은? |
| batch004_candidate | b004-15 | neither | mock | 판교역(성남) X/X | 2026년 8월 20일 새벽 2시에서 4시 사이 성남 판교역 근처의 평균 속도는? |
| batch004_candidate | b004-18 | no_lookup | mock | — | 2026년 9월 1일부터 7일까지 실차 승차가 가장 많은 시군구 세 곳은? |
| batch004_candidate | b004-19 | no_lookup | mock | — | 2026년 9월 1일부터 7일까지 손님을 가장 많이 태운 시군구 상위 3곳은? |
| batch004_candidate | b004-20 | no_lookup | mock | — | 2026년 9월 1일부터 7일까지 실차 하차가 가장 많은 시군구 세 곳은? |
| batch004_candidate | b004-21 | no_lookup | mock | — | 2026년 9월 1일부터 7일까지 시군구 기준 출발지-도착지 조합별 실차 건수가 가장 많은 다섯 노선은? |
| batch004_candidate | b004-22 | neither | mock | 대전역 X/X | 2026년 8월 한 달 동안 대전역에서 출발한 실차를 도착 읍면동별로 세면 가장 적은 두 곳은? |
| batch004_candidate | b004-23 | neither | mock | 대전역 X/X | 2026년 8월 한 달 동안 대전역에 도착한 실차를 출발 읍면동별로 세면 가장 적은 두 곳은? |
| batch004_candidate | b004-24 | mock | mock | 수성구(대구) O/X | 2026년 9월 대구 수성구 안에서 오간 실차 구간을 읍면동 출발지-도착지 조합별로 세면 가장 많은 세 개는 |
| batch004_candidate | b004-27 | neither | mock | 강남역(서울) X/X | 2026년 9월 3일 서울 강남역 근처 택시 속도는? |
| batch004_candidate | b004-28 | neither | mock | 강남역(서울) X/X | 2026년 9월 3일 서울 강남역 주변 차량 운행 속도를 알려줘 |
| batch004_candidate | b004-30 | no_lookup | mock | — | 2026년 7월 시도별 평균 수입이 가장 높은 세 곳은? |
| batch004_candidate | b004-31 | no_lookup | mock | — | 2026년 7월 수입 평균이 높은 시도 상위 3곳을 알려줘 |
| batch004_candidate | b004-34 | no_lookup | mock | — | 2026년 8월 요일별 평균 속도가 가장 낮은 요일은? |
| batch004_candidate | b004-35 | no_lookup | mock | — | 2026년 8월에 평균 속도가 제일 느렸던 요일은? |
| batch004_candidate | b004-40 | mock | mock | 대구 O/X | 지난달 대구 시군구별 공차율이 가장 높은 곳은? |
| batch004_candidate | b004-41 | mock | mock | 대구 O/X | 지난달 대구에서 공차율이 제일 높았던 시군구는 어디야? |

| 출처 | no_lookup | mock | mock_and_reference | reference_only | neither |
|---|---:|---:|---:|---:|---:|
| v003_t2pc_train | 2 | 5 | 0 | 4 | 8 |
| v003_t2pc_valid | 4 | 1 | 0 | 1 | 10 |
| batch004_candidate | 8 | 3 | 0 | 0 | 7 |
