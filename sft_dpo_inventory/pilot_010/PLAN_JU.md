# PLAN_JU — 교사 4비트 빌드(Ollama qwen3.8:27b, Q4_K_M) 대조 측정 (결정 272)

**교사 4비트 빌드의 참고 측정이며 판정이 아니다.** 이 수치로 구성·seed·조건을 고르지 않는다. **PF2·H-final의 추가 사용**(J 판정, JP·JQ·JG 사후, JT 교사 참고 다음)이며 모든 문서·표에 그렇게 적는다.
목적: 교사 응답 수집·운영에 쓴 4비트 빌드 **"Ollama qwen3.8:27b (Q4_K_M, digest `aaee06c3…`)"**(이하 Q4)가 JT에서 잰 **"Qwen/Qwen3.8-27B BF16 (vLLM)"**(이하 BF16, 결정 271)와 같은 문항에서 비슷하게 행동하는지 본다.
두 빌드는 정밀도·서버(Ollama/llama.cpp 대 vLLM)·렌더링(Ollama 내장 renderer 대 HF chat template)·sampler 구현이 다르다. 결과가 예상과 달라도 그대로 보고한다. 결과를 본 뒤 조건·규칙·범위·판정 폭을 바꾸지 않는다.
하지 않는 것: Docker·기존 컨테이너 조작, 모델 pull, 새 학습, 새 교사 응답 수집, 한도·sampling 조정, 논문 수정.

## 0. 규칙 예외(사용자 승인, 이 작업에 한함)
- 규칙 4 예외: Docker를 쓰지 않고 사용자 권한의 Ollama 서버를 새로 띄운다. 기존 "ollama" 컨테이너, 포트 11434, `/data/hwkim/ollama`는 읽기만 하고 바꾸지 않는다(쓰기·삭제·pull·prune 없음).
  2026-11-21 01:2x 확인: `docker ps -a`에 컨테이너가 없고 포트 11434는 응답하지 않는다(읽기 확인만, 아무것도 띄우거나 바꾸지 않음). `/data/hwkim/ollama/models`는 root 소유 755/644(읽기만 가능).
- 결정 114 예외: 한 셀의 문항을 GPU 4장(서버 4벌)에 나눠 잰다. "한 GPU에 작업 둘 금지"는 그대로다(GPU마다 서버 하나, 서버마다 요청 하나씩).
- 결정 83 장치 간 바이트 일치 검사는 JT와 같이 면제. UUID·드라이버·메모리·다른 프로세스 확인은 한다(`gpu_lib7.gpu_ok`, 시작 전 index → UUID 대조, 30초마다 메모리·프로세스 기록).

## 1. 1단계(GPU 없음) — 결과(`ju/setup_record.json`, `ju/record_setup_ju.py`)
- 실행 파일: 공식 GitHub release v0.40.6 `ollama-linux-amd64.tar.zst`(1,438,364,593 B, sha256 `c164ab8b…` = GitHub asset digest)를 `/data/hwkim/sftdpo_work/pilot_010_ju/ollama-0.40.6`(저장소 밖)에 `tar --zstd -xf`로 풀었다.
  설치 스크립트·systemd·root 없음. `bin/ollama` sha256 `8b4e471b…`, `ollama -v` = client 0.40.6. 교사 응답 수집(pilot_010 teacher, `tc_gpu_precheck.json`)의 서버 버전 0.40.6과 같다.
- 모델: `/data/hwkim/ollama/models`(읽기만)에서 `qwen3.8:27b` manifest(sha256 = digest `aaee06c39dcf…`)와 blob 5개(config·projector·model·license·params)를 `/data/hwkim/sftdpo_work/pilot_010_ju/models`로 복사,
  파일명(sha256)과 내용 sha256이 모두 같다. 서버가 처음 읽을 때 복사 디렉터리에 `metadata/`(blob 요약 캐시)·빈 `manifests-v2/`를 만든다(복사본 안, 원본은 그대로).
- CPU 전용 서버 확인(`CUDA_VISIBLE_DEVICES=-1`, 포트 11441, 모델 올리지 않음, 확인 뒤 내림): `/api/version` 0.40.6, `/api/tags` digest `aaee06c39dcf…`, Q4_K_M, 27.3B, `context_length` 262144,
  renderer `qwen3.8`·parser `qwen3.5`(config blob), template `{{ .Prompt }}`(내장 renderer), parameters = temperature 1·top_k 20·top_p 0.95·min_p 0·presence_penalty 0·repeat_penalty 1·draft_num_predict 4.
- **renderer 소스 확인**(v0.40.6 `model/renderers/qwen35.go`·`types/model/thinking.go`, sha256은 기록): `think: true` → 수준 "medium" → **effort 문장 없음**. think를 보내지 않을 때만 기본 xhigh 문장.
  생성 프롬프트는 `<|im_start|>assistant\n<think>\n`로 연다. 하네스 `--model-think on`과 교사 수집(`teacher/run_c10.py`, `think=True`)이 같은 요청이다. BF16(JT)은 HF chat template 기본 렌더링으로 xhigh 문장이 system 앞에 있었다.
  → **두 빌드의 system 문자열이 다르다**(Q4 = 87048d0c 본문만, BF16 = xhigh 문장 + 본문). 조정하지 않고 기록한다(사전 고정 해석 2).

## 2. 서버·요청(측정 전 고정)
- 서버 `ju/serve_ju.sh GPU PORT`: GPU i → 포트 11441 + i(GPU 0 `2445b100…`, 1 `a5ce83d0…`, 2 `c8f1bae2…`, 3 `48f798cc…`). 환경 = `CUDA_VISIBLE_DEVICES=<GPU UUID>`, `OLLAMA_HOST=127.0.0.1:<포트>`,
  `OLLAMA_MODELS=<복사 디렉터리>`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_KEEP_ALIVE=-1`, `OLLAMA_NOPRUNE=1`, `HOME=<작업 디렉터리>/home_<포트>`(`env -i`, 그 밖 변수 없음).
  기동 뒤 `/api/generate`에 model·keep_alive만(prompt 없음 → 생성 없음)으로 모델을 올리고 `/api/ps` `size_vram == size`(100% GPU), 버전·digest를 확인해 `server_<포트>.json`에
  `/api/show` parameters·template·thinking, `ollama show --parameters/--template/--modelfile`, context_length, nvidia-smi, 바이너리 sha256을 적는다. 하나라도 아니면 그 서버는 실패 → 멈춤.
  네 서버는 모델 디렉터리를 함께 읽는다. 문제가 생기면 서버마다 hard link 디렉터리(`JU_MODELS`)를 두고 그 사실을 기록한다.
- 요청 = 하네스 `evaluate_vendor100.py llm`의 Ollama 경로 그대로(`ju/ollama_eval_ju.py`): `ollama_client.OllamaClient`(`/api/chat`, `stream: false`, messages 변환 없음), `think: true`,
  문항마다 `EV._SeededClient`(options = temperature·top_p·top_k·seed, 호출 seed = `EV.call_seed(회차 seed, 문항 id, 호출 순번)` — 학생·BF16 셀과 같은 seed 값), `EV._RecordingClient`.
  pipeline = flat, `--condition-check`(condition_notes 끔), normalize·semantic 켬, mock + legacy, 운영 프롬프트 87048d0c, 지문 791c4a68 — 학생·BF16 셀과 같다.
- sampling: **S** = temperature 0.6·top-p 0.95·top-k 20(JT S, 결정 97), **G1** = temperature 0.2(같은 top-p·top-k). 회차 seed = 20261100 + k.
- 생성 상한: `num_predict` = 8,192(학생 셀 max_new_tokens, `hf_thinking.MAX_NEW_TOKENS`). thinking과 최종 답 token을 함께 센다(vLLM max_tokens와 같음).
- 기록: 호출마다 보낸 options, `done_reason`, `eval_count`, `prompt_eval_count`, total·eval·prompt_eval·load duration, decode tok/s(= eval_count / eval_duration), thinking·content 길이(`hf_calls` 자리),
  하네스 `llm_calls`(채점기가 읽음). 원문 = Ollama parser가 나눈 thinking·content(저장소 밖이나 ignore 경로). 요청 본문 예시는 messages 내용 없이(역할·길이·sha256) meta에 둔다.

## 3. 측정(`ju/driver_ju.py`, 커밋 고정 worktree, `ju/run_cell_ju.py`)
- **나누기**: 문항 i(파일 순서) → 조각 i % 4 → 서버 i % 4. 서버마다 독립된 연속 세션(결정 79, 모델을 올린 채, 요청 하나씩)이고 **한 셀 = 세션 4개**를 meta `ju.sessions`에 남긴다
  (서버 pid·시작 시각·GPU UUID·조각 문항 수·첫 응답 입력 token 확인).
- **guard**(결정 55를 Docker 없이): 서버 시작 전 host nvidia-smi로 UUID·메모리·다른 프로세스(`gpu_ok`), 모델을 올린 직후와 셀 중 60초마다 `/api/ps` `size_vram == size`(100% GPU),
  호출마다 decode tok/s. 기준: smoke = **33.71 tok/s**(같은 모델·같은 0.40.6의 교사 수집 guard 기준, `pilot_006/post/o1_speed.json` 결정 163 O1; 교사 수집 실측 66–70),
  본 측정 = smoke 호출(eval_count ≥ 64)의 decode tok/s 중앙값 × 0.5(smoke 뒤 `scope.json`에 적고 그대로 씀). eval_count ≥ 64인 호출 하나라도 기준 미만이거나 100% GPU가 아니면
  그 조각을 즉시 멈추고 원문·로그를 `ABORTED_*`로 남긴다(분석에 쓰지 않음).
- **중단된 조각**: 이어 돌리지 않는다. 실행기가 그 서버를 한 번 내렸다 다시 띄우고(새 세션, 기록) 같은 셀을 다시 실행하면 끝나지 않은 조각만 처음부터 잰다(끝난 조각은 그대로).
  두 번째도 멈추면 STOPPED. guard가 아닌 실패(코드 오류 등)는 바로 STOPPED.
- **입력 잘림 guard**: smoke의 조각마다 첫 응답(모델을 막 올린 서버의 첫 요청, prompt cache 없음)의 `prompt_eval_count`가 Ollama `qwen3.8` renderer 문자열(think true, effort 문장 없음)을
  27B HF tokenizer로 센 기대 수보다 16 넘게 적으면 멈추고 보고한다(한도를 바꾸지 않음). 모든 셀에서 서버 로그에 새 "truncat…" 줄이 생기면 멈춘다. context_length는 기동 기록에 남긴다.
- **smoke**: H-dev(`ablation_012/e2/h_dev.yaml`) 앞 100문항 × 1, S, 서버 4벌. 잘림·무효(오류 행, content 없는 호출)·처리량(문항/시간, 생성 tok/s)·decode 속도·입력 token 확인을 기록한다.
  **잘림 호출 ≥ 5% → 한도를 바꾸지 않고 멈추고 보고**(`gpu/JU/STOPPED`). 정답률은 기록만, 어떤 설정도 이 값으로 조정하지 않는다. smoke는 다시 돌리지 않는다.
- **범위 규칙**: 예상 시간 = smoke wall × 3,000 / 100(smoke도 서버 4벌) ≤ 8시간 → H-final 3,000 전체, 넘으면 JT 때 커밋한 층화 1,000문항 `jt/hfinal_subset1000_ids.txt`(sha256 `a6bea29b…`).
  부분집합이면 BF16·학생 수치도 같은 1,000문항으로 다시 계산한다(`analyze_jt.restrict`). `gpu/JU/scope.json`.
- **순서**: S PF2 150 × k=1–4(`--sealed`, 기준일 2026-10-26, 700 디렉터리 `pf2ju_s_q4_s{k}`) → S H-final(범위) × k=1(회차 seed 20261101, `--sealed`) →
  (시간이 남으면) G1 PF2 × k=1–4(각 셀 시작 시각 < **2026-11-21 20:00 KST**일 때만) → 서버 4벌 내림.
- **잘림 다시 돌리기**(JT와 같음): H-final 잘림 호출 > 1%(반올림 둘째 자리) 또는 서버 오류 행 > 1% → 같은 seed로 한 번, 원본은 `replaced/`, 결과와 무관하게 교체. PF2·smoke는 다시 돌리지 않는다.
  서버 오류 = `UNHANDLED_EXCEPTION` 중 연결·HTTP·시간 초과 예외(`completeness_B`의 이름 + httpx `ReadTimeout`·`ConnectError` 등·`OllamaRequestError`). `gpu/JU/RERUNS_JU.json`.
- PF2 접근은 시작 전에 `pilot_009/protected_final_v2/access_log.md`에 적고, PF2 셀·원문은 700 디렉터리(저장소 밖, umask 077)에 두며 내용은 열지 않는다(집계만).
- 기록: `gpu/JU/`(runs.log·gpu_check.txt·timeline.jsonl·gpu_mem.jsonl·server_*.json·server_starts.jsonl·scope.json·RERUNS_JU.json·DONE|STOPPED·셀 로그),
  셀 `cells/JU/`(smoke 하위), 원문 `training/generated/pilot_010/cells_raw_JU/`. 서버 로그는 저장소 밖(`pilot_010_ju/servers/`).
- 끝나면 새로 띄운 서버 4벌을 모두 내리고 GPU에 프로세스가 남지 않았는지 확인한다. 기존 컨테이너·포트 11434는 건드리지 않는다.

## 4. 분석(`results/analyze_ju.py`, 측정 전 커밋, 모델 호출 없음)
- Q4 단독: PF2 올바른 거부(거부 50 전체·형 M·P·C·범주 코드), 과잉 거부(답하는 100·근접 대조 25·근접 대조 범주별), 정답률(답하는 100), 결과 분해(`analyze_jp.classify` 8범주);
  H-final 정답률·과잉 거부·결과 분해·도구 유형별(·template_group 붕괴, 같은 조건 base 대비). CI = 문항 bootstrap 10,000회(`analyze_j.boot`, 교사는 행 하나 → 문항만).
- **Q4 − BF16**(같은 문항, 문항 공유 재추출): 여섯 주 지표(PF2 올바른 거부·과잉 거부 100·근접 대조 25·정답률, H-final 정답률·과잉 거부)의 차이와 95% CI.
- **유사 판정 기준**(지표마다 따로, 합쳐서 한 줄로 요약하지 않음): 순서대로 ① 차이의 95% CI 전체가 ±폭 안 → "유사", ② 아니고 CI가 0을 벗어남 → "다름", ③ 그 밖 → "판단할 수 없음".
  폭 = PF2 올바른 거부·과잉 거부(100)·정답률 **±10%p**, H-final 정답률 **±2%p**, H-final 과잉 거부 **±1%p**. "유사"이면서 CI가 0을 벗어나면 그 사실을 함께 적는다.
  근접 대조 25는 지시에 폭이 없어 차이·CI만 적고 판정하지 않는다(사전 고정 해석 7). G1(측정했으면, PF2만)도 같은 폭으로 적되 기술용이다.
- **문항별 일치**(PF2 150): 빌드마다 문항의 k=4 표본 결과(거부 / 정답 / 오답) 중 3개 이상이 같으면 그것이 다수 결과, 아니면 "혼합". 두 빌드 다수 결과가 같은 비율(혼합 = 혼합 포함)과
  혼합을 뺀 비율, 묶음별(전체·거부 50·M·P·C·답하는 100·근접 대조 아닌 75·근접 대조 25), 결과 쌍 개수표. 문항 id·내용은 저장하지 않는다.
- **학생 arm − Q4**: JT 표 2와 같은 방식(학생 U1 = arm 안 seed 재추출, Q4 문항만, 문항 공유 재추출). arm = base, SFT, RR, RR+NM4, RR+NM8(7), RR+NM 12 seed. S = J·JP·JQ 셀, G1 = JG 셀(PF2만).
  **회복 비율은 계산하지 않는다.**
- **비용**: 문항당 호출 수·wall p50·p95, 생성 token(문항당; H-final은 thinking / 최종 JSON을 각 모델 tokenizer로 나눔, PF2 원문은 나누지 않음; 학생은 arm마다 seed 표기 순서 첫째 H-final 셀),
  tok/s(Q4 = Σeval_count / Σeval_duration, 요청 하나씩; vLLM = Σ생성 / Σ호출 server_seconds, 동시 요청 묶음), GPU 메모리(측정 중 30초 표본 최대·모델 올린 직후). backend가 달라 직접 비교가 아니라고 적는다.
- **검사**: S 학생 단일 seed 평균이 `jp_posthoc.json`과 같은지(`check_against_jp`, 다르면 멈춤), BF16 S 값을 다시 계산해 `jt_results.json`과 같은지(full3000이면 여섯 지표, 부분집합이면 PF2 넷; 다르면 멈춤),
  Q4 셀 유효성(`validity_j.check` + digest·버전·think true·num_predict 8192·세션 4개·`/api/ps` 100% GPU; flashinfer 항목은 Ollama라 해당 없음).

## 5. 보고
- `results/JU_RESULTS.md`와 수치 원본 `results/ju_results.json`. 표: (1) Q4·BF16·학생 arm 결과, (2) Q4 − BF16 차이와 판정, (3) 학생 − Q4 차이, (4) 형별·범주별·도구 유형별, (5) 비용.
- 두 빌드의 요청 차이 한 절: chat template 렌더링(Ollama 내장 `qwen3.8` renderer 대 HF `chat_template.jinja`), reasoning effort 문장 유무, 입력 token 수(smoke 첫 응답 `prompt_eval_count` 대 BF16 `prompt_tokens`),
  sampler 기본값(Ollama 모델 params·서버 기본 대 vLLM `--generation-config vllm`과 명시값), 정밀도·backend·GPU 수.
- 맨 앞에 smoke와 범위 결정 근거. 계획과 달라진 점, 소요 시간. 작업 단위마다 검증 → 커밋 → push → SHA.

## 6. 사전에 정한 해석(측정 전 고정)
1. 하네스 Ollama 경로에 더한 것은 `num_predict` 8,192 하나다(하네스 `llm`은 상한을 보내지 않는다; 지시 "생성 상한은 학생 셀과 같게"). `chat_timeout` = 3,600 s(하네스 기본 300 s는 8,192 token 생성을 끊을 수 있음; 학생 vLLM client timeout과 같음).
2. `think: true` → Ollama 0.40.6 renderer가 effort 문장을 넣지 않는다(1절). BF16은 xhigh 문장이 있었다. 어느 쪽도 바꾸지 않는다. smoke 첫 응답 `prompt_eval_count`로 실제 렌더링 길이를 확인해 보고한다.
3. min_p·repeat_penalty·presence_penalty·num_ctx는 보내지 않는다(하네스 운영 options 그대로). 모델 params가 min_p 0·repeat_penalty 1·presence_penalty 0이라 S 학생·BF16 셀의 명시값(min-p 0, repetition penalty 1)과 값은 같다.
   context 길이는 서버 기본값(기동 기록의 `context_length`, 교사 수집 때 262144).
4. decode tok/s = eval_count / eval_duration(모델 올리는 시간·prompt 처리 시간 제외). eval_count < 64인 짧은 호출은 guard에서 뺀다.
5. 입력 잘림의 token 확인은 smoke 첫 응답에만 한다(Ollama가 앞 요청의 prompt를 cache로 다시 써서 뒤 요청의 `prompt_eval_count`가 작아질 수 있다). 모든 셀은 서버 로그 "truncat…" 줄로 본다.
6. 예상 시간 = smoke wall × 30(서버 4벌 그대로). smoke 처리량에는 thinking 길이가 그대로 들어간다.
7. 근접 대조 25는 판정 폭이 없어 판정하지 않는다. "유사"는 ①이 먼저다(폭 안이면 0을 벗어나도 "유사", 그 사실은 따로 표시).
8. `think_closed`는 추정이다(Ollama parser가 나눈 최종 content가 비면 닫히지 않음으로 셈). 원문 `raw_text`는 thinking·content로 다시 만든 것이다(모델 token열 그대로가 아님).
9. 모델 blob에 vision projector(931 MB)가 들어 있고 Ollama가 함께 올린다(이미지 입력 없음). 메모리 기록에 포함된다.
10. 문항별 일치의 다수 결과 = k=4 중 3개 이상(2:2·2:1:1은 혼합).
11. 학생 생성 token은 arm마다 seed 표기 순서 첫째 H-final 셀로 센다(전체 seed를 나누지 않음).
12. PF2 셀 유효성에서 flashinfer 항목은 해당 없음(Ollama). 서버 오류 이름 목록에 httpx 예외를 더했다(3절).
13. 실행 수정(2026-11-21 01:45 KST, 측정 전·결과 없음): 첫 기동에서 GPU 0용 서버가 Vulkan 장치 3개(GPU 1–3)도 찾고(0.40.6 `OLLAMA_VULKAN` 기본 true, Vulkan은 `CUDA_VISIBLE_DEVICES`를 따르지 않음)
    Vulkan backend로 모델을 GPU 1–3에 나눠 올렸다. 둘째 서버의 `gpu_ok`가 GPU 1 사용 중(12.5 GB)을 잡아 멈췄다(`gpu/JU/failed_vulkan/`). 교사 수집 컨테이너는 CUDA 장치만 보았으므로
    (`path_repeat_001/env/ollama_server.txt`: inference compute library=CUDA만) 모든 JU 서버에 `OLLAMA_VULKAN=false`를 더하고, 준비 조건에 로그의 backend = CUDA만·서버 runner 프로세스가 자기 GPU에만 있음을 더한다.
    GPU 0 단독 시험 기동(생성 없음): CUDA0만, 100% GPU(18,542,682,438 B), context 262144, GPU 0에만 35.8 GB.
