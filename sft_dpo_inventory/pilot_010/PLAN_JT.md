# PLAN_JT — 교사 모델(Qwen3.8-27B)의 봉인 셋 참고 측정 (결정 271)

**교사 참고 측정이며 판정이 아니다.** 이 수치로 구성·seed·checkpoint를 고르지 않는다. **PF2·H-final의 추가 사용**(J 판정, JP·JQ·JG 사후 다음)이며 모든 문서·표에 그렇게 적는다.
측정 모델은 **"Qwen/Qwen3.8-27B BF16 (vLLM)"** 이다. 교사 응답 생성과 운영에 쓴 **Ollama `qwen3.8:27b`(Q4_K_M, digest `aaee06c3…`)와 같은 빌드가 아니다**(정밀도·서버·tokenizer 경로·chat template 렌더링 위치가 다름). 모든 표와 문서에 이 차이를 적는다.
Ollama는 쓰지 않고 건드리지 않는다(`gpu_lib7.gpu_ok`의 `docker inspect`·`/api/ps` 읽기 확인만 기존과 같이 한다). 새 학습·새 교사 응답 수집·양자화 모델·학생 환경 vLLM 변경·X4 분석·논문 수정은 없다.
결과가 예상과 달라도 그대로 보고한다. 결과를 본 뒤 조건·규칙·범위를 바꾸지 않는다.

## 0. 결정 114·83의 예외(사용자 승인, 이 작업의 27B 서빙에 한함)
- 27B BF16(55.6 GB)은 GPU 한 장(49 GB)에 들어가지 않으므로 tensor parallel 2: **서버 A = GPU 0·1**(`2445b100…`·`a5ce83d0…`), **서버 B = GPU 2·3**(`c8f1bae2…`·`48f798cc…`). 두 서버는 설정이 같다.
- "한 GPU에 작업 둘 금지"는 그대로다. 8B 지연 셀은 GPU 한 장, 결정 114 그대로.
- 결정 83 장치 간 바이트 일치 검사는 JQ·JG와 같이 면제. UUID·드라이버·메모리·다른 프로세스 확인은 한다(`gpu_ok`, 시작 전 index → UUID 대조, 실행 중 30초마다 메모리 기록).

## 1. 1단계(JG가 도는 동안, GPU 없음)
- 진행 중인 JG 작업·스크립트는 건드리지 않는다(규칙 15). JG 파일은 이 커밋에 넣지 않는다.
- 모델: `Qwen/Qwen3.8-27B` revision `37561816e66b5b9153b1b64c10968c18c1e6f4a0`을 `/data/hwkim/sftdpo_work/pilot_010_jt/model/Qwen3.8-27B`(저장소 밖)에 내려받는다. 파일별 sha256을 계산해 Hub의 LFS sha256과 대조하고 `jt/model_manifest.json`에 적는다. 디스크 여유는 `/data` 650 GB(내려받기 전).
- vLLM 지원 확인(`jt/vllm_support.json`): 학생용 vLLM 0.30.0 환경(`runtime/envs/vllm`)의 registry에 `Qwen3_5ForConditionalGeneration`이 있고(`model_executor/models/qwen3_5.py`, Gated DeltaNet + full attention hybrid), tensor parallel은 GDN 층이 `tp_size`로 head를 나누며 head 수(attention 24·KV 4·linear V 48·K 16)가 2로 나뉜다. `--language-model-only`(0.30.0 `MultiModalConfig`)로 vision 부분을 올리지 않는다. 그 환경의 transformers 5.19.0이 `Qwen3_5Config`를 읽는다. → **별도 환경 설치 없음, 학생 환경 그대로.** 실제 기동 확인은 2단계 smoke.
- H-final 층화 부분집합 1,000문항: `jt/make_subset_jt.py` → `jt/hfinal_subset1000_ids.txt`(sha256 `a6bea29b747c…`, `hfinal_subset1000.json`). template_group 160층 비례(최대 잉여 배정), `default_rng(20261119)`. 아래 범위 규칙에서만 쓴다.

## 2. 하네스(학생 셀과 같게, 다른 점만 적음)
- 셀 실행기 `jt/run_cell_jt.py`(= `run_cell6x_g1.py` 사본), client `jt/vllm_eval_jt.py`(= `vllm_eval_pf2.py` 사본), `jt/vllm_thinking27.py`(학생 `VLLMThinkingClient` 상속, `__init__`만 다름).
  pipeline·채점기·회차 seed(20261100 + k, 호출 seed = `EV.call_seed`)·`--condition-check`·max_new_tokens 8,192·max-model-len 17,408·기록 형식·묶음 방식은 학생 셀과 같다.
- 렌더링: 학생과 같은 `render_prompt`(chat template, `enable_thinking=True`만 줌)를 **27B 자신의 tokenizer·chat template**(`chat_template.jinja`, sha256은 셀 meta)로 하고, token id열을 `/v1/completions`에 그대로 넣는다. 운영 프롬프트는 같은 87048d0c다.
  - **사전 고정 해석 1**: 27B template는 thinking 켬에서 `reasoning_effort` 기본값 xhigh의 문장("Reasoning effort is set to xhigh. …")을 system 맨 앞에 넣고, 생성 프롬프트를 `<think>\n`으로 연다. template 인자를 더 주지 않고 **이 기본 렌더링 그대로** 쓴다(설정 조정 없음). 그래서 27B의 system 문자열 = effort 문장 + 87048d0c 본문이다. 이 차이를 표에 적는다.
  - thinking 분리: 생성 원문(`skip_special_tokens=True` decode; `<think>`·`</think>`는 일반 token으로 남음을 확인)을 학생과 같은 `split_thinking`으로 `</think>` 기준으로 나눈다. 정지 token = `<|im_end|>`(248046)·`<|endoftext|>`(248044).
- 서버 `jt/serve27.sh`(= `serve_a11.sh` 사본): BF16, TP 2, `--language-model-only`, flashinfer attention·sampler, `--gpu-memory-utilization 0.85`, `--generation-config vllm`, `--seed 0`, 요청 로그. LoRA 없음, served name `teacher27`. 이미지 입력 없음.
- **서버 두 벌 나누기 규칙**: 문항 i → 묶음 i % C → 서버 (i % C) % 2. C(8·16·32)가 짝수라 문항 i는 서버 i % 2(A = 짝수 순번, B = 홀수 순번). 셀 하나의 총 동시 요청 C는 학생 셀과 같고(PF2 8, H-final 32, rdev·개발 셋 8) 서버마다 C/2.
- 조건: **S** = temperature 0.6·top-p 0.95·top-k 20(학생 주 측정), **G1** = temperature 0.2·top-p 0.95·top-k 20(JG 확정). min-p 0·repetition penalty 1.

## 3. 2단계(JG의 마지막 작업이 끝난 뒤, `jt/driver_jt.py` 순차 실행, 커밋 고정 worktree)
1. **smoke**(서버 A만): H-dev(`ablation_012/e2/h_dev.yaml`) 앞 100문항 × 1, S, 동시 16(본 H-final의 서버당 동시 수). 확인·기록: 두 장 기동, 렌더링(effort 문장 + 87048d0c + `<think>\n`), thinking 닫힘·분리, 잘림 비율, 무효 출력(`error_code` 있는 행·thinking 닫히지 않은 호출·입력 id 반향 불일치), 처리량(문항/시간, 생성 tok/s), GPU 메모리.
   - **잘림 호출 ≥ 5% → 한도를 바꾸지 않고 멈추고 보고**(`gpu/JT/STOPPED`). 정답률은 기록만, 어떤 설정도 이 값으로 조정하지 않는다. smoke는 다시 돌리지 않는다.
   - **범위 규칙**: 예상 시간 = smoke wall × (3,000 / 100) / 2(서버 2벌) ≤ 5시간 → H-final 3,000 전체, 넘으면 1절의 1,000문항 부분집합. S·G1 두 조건 모두 같은 범위. `gpu/JT/scope.json`.
2. 서버 B 기동. **실패하면 서버 A만으로 계속**(범위는 다시 계산하지 않음, 기록).
3. **S**: PF2 150 × k=1–4(동시 8, `--sealed`, 기준일 2026-10-26) → H-final(범위) × k=1(회차 seed 20261101, 동시 32, `--sealed`).
4. **G1**: PF2 k=4 → H-final k=1(JG와 같은 k).
5. **선택**(각 셀을 2026-11-20 21:00 KST 전에 시작할 수 있을 때만, S, k=1, 동시 8): refusal_dev v2 120(`pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml`) → 개발 셋 149 = valid98(98) + aux(51). 기술만 보고.
6. **지연**(4절).
- 잘림·다시 돌리기(학생 셀과 같음, `completeness_B`): H-final·개발 셋 잘림 호출 > 1%(반올림 둘째 자리) 또는 서버 오류 행 > 1%, refusal_dev v2는 잘림 ≥ 2 또는 서버 오류 ≥ 2 → 같은 seed로 한 번, 원본은 `replaced/`, 결과와 무관하게 교체. PF2는 다시 돌리지 않는다. `gpu/JT/RERUNS_JT.json`.
- 유효성: `results/validity_j.check`(프롬프트 87048d0c·fingerprint 791c4a68·커밋·flashinfer·잘림). PF2 접근은 시작 전에 `pilot_009/protected_final_v2/access_log.md`에 적고, PF2 셀은 700 디렉터리(`pf2jt_{s,g1}_t27_s{k}`, 저장소 밖)에 두며 내용은 열지 않는다(집계만).
- 기록: `gpu/JT/`(runs.log·gpu_check.txt·timeline.jsonl·gpu_mem.jsonl·server_*.json·셀 로그·DONE), 셀 `cells/JT/`(smoke·latency 하위), 원문 `training/generated/pilot_010/cells_raw_JT/`.

## 4. 지연·자원(결정 113 방식: 순차 고정 30문항)
- 고정 30문항 `serving_vllm_fp8/latency_ids.txt`(sha256 `b511a6c7…`), 동시 요청 1, S 조건, 셀마다 쓰지 않는 GPU에 다른 프로세스가 없는지 30초마다 확인(있으면 그 셀을 멈추고 기록).
- 27B: 서버 B를 내린 뒤 서버 A(GPU 0·1). 8B: 서버 A를 내린 뒤 GPU 0 하나에 `serve_a11.sh`(LoRA = RR+NM4 `o101`, seed 표기 순서 첫째, sha256 기록 대조) → base → RR+NM4 o101.
- **사전 고정 해석 2**: 같은 조건의 기존 8B 기록은 `pilot_007/latency/B2`(base·SFT o43, 2026-10-22)뿐이다. 그것은 runtime 재구성(결정 258) 전 환경이고 RR+NM 어댑터 기록이 없으므로, 같은 서버·같은 runtime에서 base와 RR+NM4를 다시 잰다. 옛 base 기록은 참고로 나란히 적는다.
- 보고: 문항 모델 시간(호출 `server_seconds` 합)과 문항 wall의 중앙값·p95, 생성 token(thinking / 최종 JSON, 각 모델 자신의 tokenizer로 나눔), tok/s(생성 합 / 모델 시간 합), 입력 token, 가중치 크기, GPU 수, 측정 중 GPU 메모리 최대(30초 표본)와 서버 기동 직후 메모리.

## 5. 분석(`results/analyze_jt.py`, 측정 전 커밋, 모델 호출 없음)
- 27B: PF2 올바른 거부(거부 50 전체, 형 M·P·C별, 범주별 — P·C 범주는 코드만), 과잉 거부(답하는 100·근접 대조 25, 근접 대조 범주별), 정답률(답하는 100), 결과 분해(`analyze_jp.classify` 범주 8개).
  H-final: 정답률, 과잉 거부율, 결과 분해, 도구 유형별, template_group 붕괴(같은 조건 base 대비). CI = 문항 bootstrap 10,000회(`analyze_j.boot`, 27B는 행 하나 → 문항만).
- 학생(새 측정 없음): 같은 문항 기준으로 기존 셀에서 다시 계산. S = J·JP·JQ sampling 셀, G1 = JG 셀. arm = base, SFT(B2F 5), RR(P9 5), RR+NM4(V4 5), RR+NM8(7), RR+NM 12 seed 합침. H-final이 부분집합이면 학생도 그 1,000문항.
- 차이: 각 학생 arm − 27B(`analyze_j.diff`: 학생은 U1 = arm 안 seed 재추출, 27B는 문항만, 문항 공유 재추출). 조건별(S, G1) 따로. **"교사 대비 회복 비율"은 계산하지 않는다**(값과 차이만).
- 검사: S 학생 단일 seed 평균(3,000문항)이 `jp_posthoc.json`과 같은지(다르면 멈춤). 27B 셀 유효성.
- 선택 셀(rdev v2·valid98·aux): 27B 단독 기술(정답률·거부 결과 비율·잘림). smoke 기록.

## 6. 보고
- `results/JT_RESULTS.md`와 수치 원본 `results/jt_results.json`. 표: (1) 27B와 학생 arm의 PF2·H-final 결과(조건별), (2) 학생 − 27B 차이, (3) 형별·범주별·도구 유형별, (4) 지연·자원.
- 교사 응답 수집 방식 한 절(새 측정 아님): 답하는 질의·거부 질의·근접 대조 질의 각각의 교사 지시 파일, 결론을 주었는지, 수집 수·통과 수, 모델 빌드, 관련 결정 번호.
- 맨 앞에 smoke와 범위 결정 근거, 렌더링 차이, 빌드 차이. 계획과 달라진 점, 소요 시간. 작업 단위마다 검증 → 커밋 → push → SHA.

## 7. 사전에 정한 해석과 대비(측정 전 고정)
1. 27B chat template 기본 렌더링(effort xhigh 문장 포함) 그대로(2절).
2. 8B 지연은 같은 runtime에서 다시 잰다(4절).
3. smoke 동시 16, 예상 시간 = smoke wall × 30 / 2(3절). smoke 처리량에는 thinking 길이가 그대로 들어간다.
4. 서버 B 기동 실패 → 서버 A만으로 계속(범위 그대로).
5. 27B 서버가 FLASHINFER attention으로 뜨지 않으면 attention backend 자동 선택(`ATTN=auto`, 다른 인자 같음)으로 한 번만 다시 띄우고, 이후 이 작업의 모든 27B 서버를 그 설정으로 둔다(학생 셀과 커널이 다름을 표에 적음). 그것도 실패하면 멈추고 보고한다.
6. 개발 셋 149 = valid98 98 + aux 51(JP E-A와 같은 두 gold). 선택 셀 마감 2026-11-20 21:00 KST(시작 시각 기준).
7. PF2 27B는 k=4(학생 어댑터 셀과 같음; J의 base k=8과 다름).
