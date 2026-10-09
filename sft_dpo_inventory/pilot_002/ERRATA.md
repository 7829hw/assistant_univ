# pilot_002 정정

`REPORT.md`와 다른 기존 기록은 고치지 않는다. 정정은 이 문서에만 적는다.

## 1. HF 경로의 GPU 2·3 출력 일치(2026-10-09)

**틀린 기술.** "HF 경로에서 GPU 2와 GPU 3이 같은 출력을 내는지는 확인된 적이 없다."
- 이 문장(또는 같은 뜻)이 있는 곳:
  - 2026-10-09 최종 보고의 사람 검토 항목 4.
  - `REPORT.md` 8절("HF 경로의 GPU 2·3 출력 일치는 확인되지 않았다(`../pilot_001_analysis/REPORT.md` e절)").
  - `REPORT.md` 10절("HF 경로의 GPU 2·3 출력 일치는 확인되지 않았으므로, DPO 선택(144)에 장치 차이가 섞였을 수 있다").
  - `../VENDOR100_ACCURACY.md` pilot_002 절 표 4 아래("HF 경로의 GPU 2·3 출력 일치는 확인되지 않았습니다").

**바른 사실.** 결정 43에서 이미 확인했다.
- pilot_001 SFT step 124를 GPU 2에서 valid98로 다시 재서 GPU 3 기록과 비교했다.
- 첫 응답 원문과 모든 호출(재질의 포함)이 98/98문항 바이트 단위로 같았다. grounding_ok 61 → 61, 결과 종류 98/98 일치.
- 조건: 같은 torch·CUDA 빌드(2.11.0+cu128), bf16, sdpa, greedy, 두 RTX 6000 Ada.
- 기록: `../pilot_001_analysis/REPORT.md` 6절 a, `../pilot_001_analysis/decision43/`(`sft_step124_gpu2.json`, `comparison.json`).
  위 문장들이 근거로 든 같은 문서의 3절 e("미확인")는 6절 a 이전에 쓴 것이다.

**범위.** 한 checkpoint(pilot_001 SFT 124), 98문항에서 확인한 것이다.
- pilot_002의 adapter(SFT checkpoint-380, DPO checkpoint-144 등)에도 같다고 단정하지 않는다.
- 그래서 pilot_002의 장치 관련 기술은 다음처럼 읽는다.
  - selection_v1 평가가 GPU 2·3에 섞인 것(DPO 144·288은 GPU 3, 나머지는 GPU 2): 결정 43의 확인으로 보면 장치 때문에 선택이 바뀌었다는 근거는 없다.
    다만 pilot_002 checkpoint로 직접 확인하지는 않았다.
  - HF-E(GPU 2)와 pilot_002 HF 셀(GPU 3), pilot_001 HF 셀(GPU 2)과 pilot_002 HF 셀(GPU 3)의 장치 차이도 같다.
- 판정, 선택 결과, 숫자는 바뀌지 않는다.
