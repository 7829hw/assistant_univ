# 지연 측정 도구(C8, D8)

`latency6.py`: base·F·P를 한 서버(17,408, F·P LoRA)에서 순차 고정 30문항(동시 요청 1)으로 연달아 잰다. 다른 두 GPU에 프로세스가 있으면(시작 전·셀마다·측정 중 30초마다) 멈추고 exit 3.
기록: 문항 모델 시간 중앙값과 base 대비 비(D8 ≤ 1.5), 생성·입력·thinking·최종 JSON token 중앙값, 셀 구간 prefix cache 적중률(서버 로그).

검증(GPU 없이): `--test-fake`로 OpenAI 호환 가짜 서버를 띄워 세 셀을 돌렸다(`fake_test/latency_summary.json`). 흐름·기록 형식 정상, 입력 token은 Full 7,284 / Partial 8,743
(P0.3 prompt가 실제로 쓰임). 측정값(0.023초)은 가짜라 의미 없다. 적중률 파서는 `tests/test_latency6.py`.
세션 3: F·P adapter를 `LORAS="F=<경로> P=<경로>"`로 `serve6b.sh`에 올리고, 다른 두 GPU를 비운 뒤 실행한다(약 40분).
