# reviewed_gold_v001

사용자가 PRODUCT_DECISIONS_001 정책을 채택하고 최종 검증·확정·import를 명시적으로 위임한 첫 reviewed semantic corpus다. 실제 의미/구조 재검증은 Codex가 수행했다. 사람이 각 모델 출력을 직접 열람했다고 추정하지 않는다.

Decision audit은 accepted 19 / needs_fix(hold) 11 / rejected 0이다. 19 records는 gold/pair 중복 제거 후 SFT 14 questions + DPO 5 pairs다. SFT train/valid=10/4, DPO=2/3; seed=42, group-level valid_fraction=0.2. DPO는 SFT split을 상속한다. 원본 queue는 immutable pending이며 실제 최종 상태는 별도 review_decisions.jsonl audit에 있다. 원본 pilot corpus와 미검토 synthetic pair는 병합하지 않았다.

- manifest.json: SFT/DPO training provenance, coverage, output hashes.
- corpus_manifest.json: import/protection/split와 완성된 version 파일 hashes.
- reviewed_annotations.yaml: 중복 제거한 14 reviewed semantic golds.
- review_decisions.jsonl: 사용자의 명시적 정책 채택·검증 위임에 근거한 30건 decision audit.
- policy_and_scope.json: semantic gold와 execution benchmark 분리. RB001-21–24의 명시적 실행 제외와 reference/mock 범위; raw planner JSON에 넣지 않는다.
- coverage_before_after.json: frozen historical 15 questions, 실제 재검토된 9 old questions, v001 14 questions의 분포/갭 비교.
- validation_report.json: CPU strict builder/parse/compose/G1–G7/leakage 및 테스트 결과.

RB001-10–16은 통계 정의, 17–20은 RPM 원래 공간 의도가 미확정이라 hold다. Diagnostic-only 보호 50건은 들어 있지 않다. Grounding target이나 production prompt/schema는 바꾸지 않았다.

OD scope 2 questions는 train, dimension-only 3 questions는 validation으로 분리되었다. 전체 5 DPO pair는 semantic negative이며 constraint negative가 아니다. DPO train 2 pairs만으로 일반적인 DPO 효과를 결론 내리지 않는다.

새 validation의 RB001-05는 과거 pilot train에 있던 질문이다. 다음 SFT는 Base에서 새로 시작하고, DPO는 그 새 SFT adapter에서 시작해야 한다. 이전 pilot SFT/DPO adapters의 새 validation 점수를 unseen 결과라고 부르면 안 된다. v001 validation은 이후 corpus version에서 기존 Protection이 계속 보호한다.

Execution benchmark scope는 별도 sidecar이고 현재 evaluator가 이를 자동 적용하지 않는다. RB001-21–24는 실행 benchmark에서 제외한다. Reference 03/04는 합성 데이터 계산 검증 범위이고 실제 TIMS나 unseen benchmark가 아니다. 다른 mock 실행도 배선 확인이며 실제 통계 정답 검증은 아니다. 지원 진단에서 실패를 삭제해 성공률 분모를 줄이지 않는다.

검증에는 기존 SFT builder --strict와 기존 DPO builder strict=True를 사용했다. DPO strict 검증은 별도의 process-local candidate replay harness로 이미 검토된 5 negative만 재사용했고 새 synthetic negative를 생성하지 않았다. 이 harness와 strict manifests는 review_batch_001/validation_evidence_001에 있다. Standalone builder의 validation-only /tmp outputs를 학습 corpus로 사용하지 말고 이 importer 산출물을 사용한다.

다음 pilot의 데이터 검사는 PASS다. 실행 전 새 dataset 경로/config/model/prompt/decoding/seed를 동결하고 동일 조건의 Base를 재측정해야 한다. 이번 단계에서는 config 변경, GPU 학습, 모델 inference를 실행하지 않았다. 이 dataset은 작은 OD 중심 pilot 용도이며 production 품질 검증이나 독립 최종 holdout을 대체하지 않는다.
