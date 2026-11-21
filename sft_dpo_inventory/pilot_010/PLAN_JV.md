# pilot_010 JV — 학생 4비트 빌드(Ollama, Q4_K_M) 측정, 교사 4비트 빌드(JU)와 같은 조건 (결정 273)

**학생 4비트 빌드의 참고 측정이며 판정이 아니다.** 이 수치로 구성·seed·조건을 고르지 않는다. 운영 경로(결정 76, HF BF16)를 바꾸지 않는다.
**PF2·H-final의 추가 사용**(J 판정, JP·JQ·JG 사후, JT·JU 교사 참고 다음)이며 모든 문서·표에 그렇게 적는다. 결과가 예상과 달라도 그대로 보고한다.
이 계획·규칙·분석 스크립트는 측정 전에 커밋한다(변환 스크립트·이 계획 = 첫 커밋, 서버·client·driver·분석 = 측정 전 둘째 커밋, `FREEZE_JV.json`).

## 0. 범위·규칙 예외
- 목적: (1) 학생과 교사를 같은 정밀도(Q4_K_M)·같은 서버(Ollama 0.40.6, Docker 없는 사용자 권한 서버, JU와 같은 실행 파일)에서 재 속도·메모리 차이를 본다.
  (2) 학생의 거부·과잉 거부·정답률이 4비트 빌드에서도 유지되는지 본다.
- 규칙 4 예외(이 작업에 한함): JU의 Ollama 0.40.6(`/data/hwkim/sftdpo_work/pilot_010_ju/ollama-0.40.6`, tar sha256 `c164ab8b…`)로 서버를 띄우고, 새 모델 디렉터리
  `/data/hwkim/sftdpo_work/pilot_010_jv/models`에 `geoflow-jv-…` 이름으로 등록한다. 기존 컨테이너·포트 11434·`/data/hwkim/ollama`는 읽기만(공식 qwen3:8b blob 타입 대조).
  pull 없음. 교사 Q4(지연 셀)는 JU 모델 디렉터리(`pilot_010_ju/models`)를 그대로 쓴다(새로 받거나 등록하지 않음).
- 결정 114 그대로: 모델 하나의 셀은 GPU 한 장·서버 한 벌에서 처음부터 끝까지, GPU 4장에 모델 네 개 동시. 한 GPU에 작업 둘 금지. 결정 83 바이트 일치 검사 면제(JU와 같음),
  UUID·드라이버·메모리·다른 프로세스 확인은 한다.
- 하지 않는 것: Docker·기존 컨테이너 조작, 모델 pull, 새 학습, 양자화 방식·한도·sampling 조정, seed 고르기, 운영 경로 변경, 논문 수정.

## 1. 대상 모델과 변환(1단계, CPU)
- 대상(결과와 무관하게 고정, `jv/models_jv.py`): 필수 11 = base Qwen3-8B@b968826d, SFT(B2F) o43·o1016·o7·o11·o2027, RR+NM4(V4) o101·o523·o2029·o31·o20271027.
  선택 7 = RR+NM8(V8) o43·o1016·o7·o3110380·o1821915·o5415284·o3616422. adapter = 학생 BF16 셀이 쓴 checkpoint(`gpu/JG/adapters_check_main.json`, sha256 대조).
- 줄이는 규칙: smoke 뒤 필수 전체 예상 시간(3절) > 14시간이면 SFT·RR+NM4를 위 순서 앞 3 seed(o43·o1016·o7, o101·o523·o2029)로 줄인다. 그 밖의 이유로 고르지 않는다.
- 변환(`jv/convert_jv.py`, CPU만): `training.merge_adapter`(bfloat16, CPU) → `pilot_prep_001/gguf_convert.sh`(바꾸지 않음) `QUANT_RECIPE=official`
  (= `llama-quantize --tensor-type attn_v=f16 BF16.gguf Q4.gguf Q4_K_M`, imatrix 없음; `quant_recipe/RECIPE.md`). llama.cpp = 결정 258 rebuilt runtime
  `runtime/native/llama.cpp-b11434`(commit `5e03bdd8`, 결정 75와 같은 tag), 변환 Python = `runtime/envs/llamacpp`(환경 변수 `LLAMA_CPP_DIR`·`VENV`로 넘김; 스크립트 기본 경로는 결정 258로 없어짐).
  base는 병합 없이 pilot_prep_001 BF16 GGUF(`4bed31be…`, 읽기만)에서 `FROM_BF16`으로 양자화하고 결정 75 base 공식 방식 Q4(`c55752ae…`)와 sha256이 같은지 적는다.
- 확인: 모델마다 텐서 399개의 이름·모양·타입이 공식 qwen3:8b blob(`a3de86cd…`)과 모두 같아야 등록한다(`jv/compare_types_jv.py`, `quant_recipe/compare_types.py`와 같은 비교).
  영수증 `jv/receipts/<name>.json`(adapter sha256, 병합·변환·양자화 명령, BF16·Q4 sha256·바이트, 타입 구성). Q4 확인 뒤 이 작업이 만든 병합본·BF16 GGUF만 지운다.
  가중치는 모두 저장소 밖(`/data/hwkim/sftdpo_work/pilot_010_jv/{merged,gguf,models}`). 디스크 여유 확인(시작 시 578 GB, 동시 3개 × 약 40 GB).
- 등록(`jv/register_jv.py`): CPU 전용 서버(`CUDA_VISIBLE_DEVICES=-1`, `OLLAMA_VULKAN=false`, 포트 11460, `OLLAMA_MODELS` = JV 디렉터리)에서 `POST /api/blobs` + `POST /api/create`
  (`ollama create`와 같음). Modelfile = 결정 75의 hfthink(`quant_recipe/registration/base_official_q4.json`의 TEMPLATE·PARAMETER 그대로: stop `<|im_start|>`·`<|im_end|>`,
  temperature 0.6·top_k 20·top_p 0.95·repeat_penalty 1). `/api/show`(template·parameters·capabilities·details·renderer/parser 필드 유무)와 digest를 `jv/registration/<name>.json`에 남기고 서버를 내린다.

## 2. 렌더링·요청 확인(2단계, 측정 전)
- 요청 = 하네스 Ollama 경로(JU client의 사본 `jv/ollama_eval_jv.py`): `OllamaClient`(`/api/chat`, stream false, `think: true`) + `EV._SeededClient`(호출 seed = `EV.call_seed`) +
  `EV._RecordingClient`, 운영 프롬프트 87048d0c, `num_predict` 8,192, S = temperature 0.6·top-p 0.95·top-k 20.
  **min_p 0·presence_penalty 0·repeat_penalty 1은 요청 options로 명시**한다(`_SeededClient`의 `extra_options`; 호출마다 `options_sent`에 남음). Modelfile PARAMETER는 결정 75 그대로 둔다.
  회차 seed = 20261100 + k(PF2 k=1–4, H-final·smoke·지연 k=1) — 학생 BF16 셀·JU와 같은 값.
- 렌더링: 모든 셀에서 문항마다 **첫 호출**(messages = system + user)의 `prompt_eval_count`를 HF chat template(Qwen3-8B@b968826d tokenizer, `training.trainer_common.render_prompt`와 같은
  `apply_chat_template(add_generation_prompt=True, enable_thinking=True)`)로 센 token 수와 비교한다. JU 셀에서 `prompt_eval_count`는 cache와 상관없이 전체 prompt 길이였다
  (PF2 첫 호출 중앙값 6,619 — PLAN_JU 6절 5의 가정과 다름). **차이가 0이 아니면 그 조각을 즉시 멈춘다(exit 4)**. 2단계 확인은 base Q4, H-dev 앞 5문항 셀(`render/`, S, k=1).
  `/api/show`에 renderer·parser가 없고 template이 hfthink와 같아야 한다. 다르면 원인을 기록하고, 맞출 수 없으면 측정하지 않고 보고한다.
- thinking·JSON 나눔: 같은 5문항 첫 호출 messages를 HF template으로 렌더링해 `/api/generate`(`raw: true`, 같은 options·seed)로 다시 생성하고, 원문을 학생 vLLM 셀과 같은
  `hf_thinking.split_thinking`(`</think>` 기준)으로 나눈 값이 `/api/chat`의 `thinking`·`content`와 같은지 본다. 생성이 같지 않으면(비결정성) 그 사실과 구조 검사
  (content에 `<think>`·`</think>` 없음, thinking이 `<think>`로 시작하지 않음, 원문 나눔 결과의 구조)를 기록한다.
- sampler: llama-server 로그의 요청마다 `sampler params` 줄에서 temp·top_k·top_p·min_p·repeat_penalty·presence_penalty를 읽어 기대값과 같은지 센다(셀마다, 보고).
  기본 로그에 그 줄이 없으면(엔진이 다르면) 모든 JV 서버에 `OLLAMA_DEBUG=1`(로그만 바뀜)을 더하기로 2단계에서 정하고 기록한다.

## 3. 측정(3단계)
- 서버(`jv/serve_jv.sh`, `ju/serve_ju.sh`의 사본): GPU마다 한 벌, JU와 같은 환경 변수(`CUDA_VISIBLE_DEVICES=<UUID>`, `OLLAMA_NUM_PARALLEL=1`, `MAX_LOADED_MODELS=1`, `KEEP_ALIVE=-1`,
  `NOPRUNE=1`, `VULKAN=false`, 사용자 HOME), 포트 11461–11464(GPU 0–3). 준비 조건 = 버전 0.40.6·digest·100% GPU·backend CUDA만·runner가 자기 GPU에만. context = 서버 기본값(기록).
- 작업 = (모델, 단계): PF2 작업 = 그 모델 PF2 150 × k=1–4 네 셀을 한 서버 세션에서 차례로, H-final 작업 = 층화 1,000(`jt/hfinal_subset1000_ids.txt`) × k=1 한 셀.
  작업마다 서버를 새로 띄우고(모델 하나) 끝나면 내린다. 대기열 순서 = 필수 PF2(모델 목록 순서) → 필수 H-final → 선택 PF2 → 선택 H-final. GPU 4장이 빈 대로 다음 작업을 가져간다(5분 안).
  **사전 고정 해석 1**: "필수가 끝난 뒤"는 필수 작업이 모두 시작된 뒤(대기 중인 필수 작업이 없을 때) 빈 GPU에서 선택 작업을 시작하는 것으로 한다(필수를 늦추지 않음).
  선택 작업은 2026-11-22 12:00 KST 전에만 시작한다. 선택 arm은 V8 순서의 앞에서부터 PF2·H-final이 모두 끝난 seed만 쓴다(중간이 빠지면 그 앞까지).
- guard(JU와 같음): 작업 시작 전 host nvidia-smi(UUID·메모리·다른 프로세스, `gpu_ok`), 모델을 올린 뒤 `/api/ps` 100% GPU, 측정 중 60초마다 `/api/ps`(100% 아니면 멈춤),
  30초마다 GPU 메모리 기록과 그 GPU의 다른 프로세스 검사(우리 서버가 아니면 멈춤), 호출마다 생성 속도(eval_count ≥ 64에서 decode tok/s < 기준이면 ABORTED, exit 3),
  입력 잘림(첫 호출 렌더링 차이 ≠ 0, 서버 로그 `truncating input`·`truncated = [1-9]`). 멈춘 작업은 서버를 한 번 다시 띄워 끝나지 않은 셀을 처음부터 다시 잰다(두 번째면 그 작업만 멈추고 보고).
- 속도 기준: smoke = 30 tok/s(pilot_002 8B Q4 GPU 기준, `pilot_002/PLAN_DEVIATIONS.md`), 본 측정 = smoke 호출 decode 중앙값 × 0.5. 교사 지연 셀 = JU 본 측정 기준 48.85 tok/s.
- smoke: base Q4, GPU 0, H-dev 앞 100 × 1(S, 회차 seed 20261101). 잘림·무효(오류 행)·처리량 기록. **잘림 ≥ 5%면 한도를 바꾸지 않고 멈추고 보고**. 정답률은 기록만.
- 필수 예상 시간 = smoke wall × (600 + 1,000) / 100 × 필수 모델 수 11 / 4(GPU) (`gpu/JV/scope.json`). > 14시간이면 1절의 줄이는 규칙.
- 잘림 다시 돌리기(JU와 같음): H-final 잘림 호출 > 1% 또는 서버 오류 행 > 1%면 같은 seed로 한 번(새 세션), 원본은 `replaced/`, 결과와 무관하게 교체. PF2·smoke는 다시 돌리지 않는다.
- 셀 위치: PF2 `/data/hwkim/sftdpo_work/protected_final_v2/cells/pf2jv_<arm>_<seed>_q4_s<k>.json`(base = `pf2jv_base_q4_s<k>`, umask 077, `--sealed`, 기준일 2026-10-26, 원문 `raw/`),
  H-final `cells/JV/hfinaljv_<arm>_<seed>_q4_s1.json`(원문 `training/generated/pilot_010/cells_raw_JV/`), smoke `cells/JV/smoke/`, 렌더링 확인 `cells/JV/render/`, 지연 `cells/JV/latency/`.
  PF2 접근은 `pilot_009/protected_final_v2/access_log.md`에 적고 내용은 열지 않는다.
- 지연·자원(결정 113 방식, 모든 작업이 끝난 뒤 다른 GPU 작업 없이 GPU 0 한 장에서 차례로): 교사 Q4(`qwen3.8:27b`) → base Q4 → RR+NM4 o101 Q4. 고정 30문항
  (`serving_vllm_fp8/latency_ids.txt`, `conversion_diag/selection_gold.yaml`, 기준일 2026-09-25), 동시 1, S(회차 seed 20261101), 서버 한 벌, **context 17,408**(서버 환경 `OLLAMA_CONTEXT_LENGTH=17408`,
  `/api/ps` context_length로 확인), 같은 요청 options. 문항당 모델 시간(호출 total_duration 합)·wall 중앙값·p95, 생성 token(thinking / 최종 JSON, 각 모델 tokenizer), tok/s(Σeval_count / Σeval_duration),
  입력 token, 가중치 파일 크기, 모델 올린 직후·측정 중(5초 표본) GPU 메모리, 교사의 speculative decoding 여부(서버 로그 `--spec-type`).
- 끝나면 새로 띄운 서버를 모두 내리고 GPU에 프로세스가 남지 않았는지 확인한다.

## 4. 분석(`results/analyze_jv.py`, 측정 전 커밋, 모델 호출 없음)
- H-final은 모두 JT 층화 1,000문항(`AT.restrict`). 교사 Q4(JU S 셀)·학생 BF16(S = J·JP·JQ 셀) 수치도 같은 1,000문항으로 다시 계산한다.
- 학생 Q4 arm별(base, SFT, RR+NM4, 선택 시 RR+NM8·RR+NM 12 seed 합침): PF2 올바른 거부(전체·M·P·C), 과잉 거부(답하는 100·근접 25), PF2 정답률, H-final 정답률·과잉 거부,
  결과 분해(`analyze_jp.classify`), 도구 유형별, 범주별. CI = U1 bootstrap 10,000회(`analyze_j.boot`: 문항 공유, arm 안 seed 재추출).
- **같은 어댑터 Q4 − BF16(seed·문항 짝)**: arm마다 seed s의 Q4 문항 값 − 같은 seed BF16 문항 값의 행렬(seed × 문항)로 `analyze_j.est`(seed·문항 함께 재추출). 여섯 주 지표, 판정 문구 없이 값만.
  base는 BF16 PF2 k=1–4·H-final s1과 짝(같은 회차 seed; Q4 base도 k=1–4·s1). 짝의 회차 seed가 같은지 셀 meta로 확인한다(다르면 멈춤).
- Q4 안 arm 차이(`analyze_j.diff`, 짝 없음): RR+NM − SFT, RR+NM − base, SFT − base. RR+NM = RR+NM4(선택 arm이 모두 있으면 RR+NM 12 seed도). BF16의 같은 차이를 나란히 둔다.
- 학생 Q4 − 교사 Q4(JU): JU 표 3과 같은 방식(학생 U1, 교사 문항만, 문항 공유 재추출). 회복 비율은 계산하지 않는다.
- 지연·자원 표: 교사 Q4 대 학생 Q4(같은 서버·같은 context 17,408). 참고로 BF16 vLLM 수치(`jt_results.json` latency, JT 표 4)를 나란히 둔다.
- 비용(측정 셀): arm마다 문항당 호출 수·wall p50·p95·decode tok/s(Σeval_count/Σeval_duration)·생성 token(H-final thinking / JSON, 8B tokenizer), 측정 중 GPU 메모리 최대.
- 검사: 학생 BF16 S 단일 seed 평균이 `jp_posthoc.json`과 같은지(`check_against_jp`, 전체 3,000), 교사 Q4 S 여섯 지표(전체 3,000)가 `ju_results.json`과 같은지(다르면 멈춤),
  JV 셀 유효성(`validity_j.check` + digest·버전·think·num_predict·extra options·첫 호출 렌더링 차이 0·100% GPU·세션 1·sampler 로그 값).

## 5. 보고
- `results/JV_RESULTS.md`와 수치 원본 `results/jv_results.json`. 표: (1) 학생 Q4·학생 BF16·교사 Q4 결과, (2) Q4 − BF16, (3) Q4 안 arm 차이, (4) 학생 Q4 − 교사 Q4, (5) 지연·자원, (6) 형별·도구 유형별.
- 변환·등록·렌더링 확인 기록, 계획과 달라진 점, 소요 시간. 작업 단위마다 검증 → 커밋 → push → SHA.

## 6. 사전에 정한 해석(측정 전 고정)
1. 3절 "필수가 끝난 뒤" 해석·선택 시작 마감·선택 arm 규칙.
2. Q4 − BF16 짝: seed 이름이 같은 셀끼리, base는 회차 seed 20261101–20261104·20261101. 학생 BF16 표 1의 arm 수치는 JT·JU와 같은 정의(base PF2 8·H-final 2)로 둔다.
3. 렌더링 비교는 첫 호출만(재시도·수리 호출은 앞 응답을 담아 HF 렌더링과 비교 대상이 아님).
4. decode tok/s = eval_count / eval_duration(prompt 처리 제외), eval_count < 64인 호출은 guard에서 뺀다(JU와 같음).
5. `think_closed`는 추정(Ollama parser의 content가 비면 닫히지 않음), 원문 `raw_text`는 thinking·content로 다시 만든 것(JU와 같음).
6. 교사 지연 셀은 JU 모델 디렉터리·JU와 같은 실행 파일, context만 17,408(지시). speculative decoding(MTP)은 서버 기본값 그대로(바꾸지 않음, 기록).
