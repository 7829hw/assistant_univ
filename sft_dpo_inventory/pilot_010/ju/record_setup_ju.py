# -*- coding: utf-8 -*-
"""pilot_010 JU(결정 272, PLAN_JU 1절) 준비 기록(GPU 없음, 모델 호출 없음) → ``ju/setup_record.json``.

    python3 sft_dpo_inventory/pilot_010/ju/record_setup_ju.py

- Ollama 실행 파일: 공식 GitHub release v0.40.6 ``ollama-linux-amd64.tar.zst``(설치 스크립트·systemd·root 없이 작업 디렉터리에 품)의 sha256과
  GitHub release asset digest 대조, 푼 ``bin/ollama`` sha256, ``ollama -v``.
- 모델: ``/data/hwkim/ollama/models``(읽기만)의 ``qwen3.8:27b`` manifest와 blob 5개를 새 디렉터리로 복사, 파일명(sha256)과 내용 sha256 대조, manifest sha256 = digest.
- CPU 전용 서버 확인(``CUDA_VISIBLE_DEVICES=-1``, 포트 11441, 모델 올리지 않음): ``/api/version``·``/api/tags`` digest·``/api/show``(parameters·template·thinking).
- renderer 소스(v0.40.6 ``model/renderers/qwen35.go``·``types/model/thinking.go``): ``think: true`` → 수준 "medium" → effort 문장 없음,
  think를 보내지 않으면 기본 xhigh 문장. 파일 sha256과 해당 줄.
"""
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
JU = Path("/data/hwkim/sftdpo_work/pilot_010_ju")
SRC_MODELS = Path("/data/hwkim/ollama/models")
TAR_DIGEST_GITHUB = "c164ab8b1b28e2a247c29719b8e404c423c5b83ae64c3ab4e59d50c7ff7fc5e0"   # gh api repos/ollama/ollama/releases/tags/v0.40.6 asset digest
MANIFEST = "manifests/registry.ollama.ai/library/qwen3.8/27b"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def lines_with(path, keys):
    return [f"{i + 1}: {l.rstrip()}" for i, l in enumerate(Path(path).read_text(encoding="utf-8").splitlines()) if any(k in l for k in keys)]


def main():
    tar = JU / "dist/ollama-linux-amd64.tar.zst"
    binp = JU / "ollama-0.40.6/bin/ollama"
    man = json.loads((JU / "models" / MANIFEST).read_text(encoding="utf-8"))
    blobs = {}
    for layer in [man["config"]] + man["layers"]:
        d = layer["digest"].split(":", 1)[1]
        dst, src = JU / "models/blobs" / f"sha256-{d}", SRC_MODELS / "blobs" / f"sha256-{d}"
        h = sha(dst)
        blobs[d] = {"mediaType": layer["mediaType"], "size": layer["size"], "copy_size": dst.stat().st_size, "copy_sha256_ok": h == d,
                    "source_size_equal": src.stat().st_size == dst.stat().st_size}
    show = json.loads((JU / "logs/show_cpu.json").read_text(encoding="utf-8"))
    src = JU / "src_v0.40.6"
    rec = {"decision": 272, "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "ollama_binary": {"release": "https://github.com/ollama/ollama/releases/download/v0.40.6/ollama-linux-amd64.tar.zst",
                             "tar_sha256": sha(tar), "tar_bytes": tar.stat().st_size, "github_asset_digest": TAR_DIGEST_GITHUB, "tar_digest_ok": sha(tar) == TAR_DIGEST_GITHUB,
                             "extracted_dir": str(JU / "ollama-0.40.6"), "bin_ollama_sha256": sha(binp),
                             "version_cli": subprocess.run([str(binp), "-v"], capture_output=True, text=True).stderr.strip().splitlines()
                             + subprocess.run([str(binp), "-v"], capture_output=True, text=True).stdout.strip().splitlines(),
                             "install": "tar --zstd -xf (설치 스크립트·systemd·root 없음)"},
           "model": {"source_dir(read only)": str(SRC_MODELS), "copy_dir": str(JU / "models"), "manifest_path": MANIFEST,
                     "manifest_sha256(copy)": sha(JU / "models" / MANIFEST), "manifest_sha256(source)": sha(SRC_MODELS / MANIFEST),
                     "digest_expected": "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813", "blobs": blobs,
                     "all_blobs_ok": all(b["copy_sha256_ok"] for b in blobs.values()), "manifest": man,
                     "note": "서버가 처음 읽을 때 복사 디렉터리에 metadata/(blob 요약 캐시)·manifests-v2/(빈 디렉터리)를 만든다. 원본 디렉터리는 root 소유·읽기만."},
           "cpu_server_check": {"env": "CUDA_VISIBLE_DEVICES=-1 OLLAMA_HOST=127.0.0.1:11441 OLLAMA_MODELS=<copy> (모델을 올리지 않음, 확인 뒤 내림)",
                                "api_show": {k: show.get(k) for k in ("parameters", "template", "thinking", "capabilities", "details", "requires")},
                                "api_show_modelfile_head": "\n".join((show.get("modelfile") or "").splitlines()[:8]),
                                "log_head": (JU / "logs/cpu_check_11441.log").read_text(errors="replace").splitlines()[:30]},
           "renderer_source_v0.40.6": {
               "files": {f: sha(src / f) for f in ("qwen35.go", "qwen38_test.go", "renderer.go", "thinking.go", "api_types.go")},
               "qwen35.go": lines_with(src / "qwen35.go", ("qwen38XHighReasoningInstructions", "qwen38LowReasoningInstructions", 'case "medium"', 'case "xhigh"',
                                                           "think == nil || think.Value == nil", "Default: \"xhigh\"", "<think>\\n\")")),
               "thinking.go": lines_with(src / "thinking.go", ('return "medium"',)),
               "qwen38_test.go": lines_with(src / "qwen38_test.go", ('{name: "true"', '{name: "xhigh"')),
               "conclusion": ("think=true(하네스 --model-think on, 교사 수집 run_c10.py think=True와 같음) → ThinkValue.String() = 'medium' → qwen38ReasoningInstructions = '' "
                              "→ system에 effort 문장 없음. think를 보내지 않을 때만 기본 xhigh 문장. 생성 프롬프트는 '<|im_start|>assistant\\n<think>\\n'로 연다. "
                              "BF16(JT, HF chat template 기본 렌더링)은 xhigh 문장이 system 앞에 있다.")}}
    (HERE / "setup_record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"tar_digest_ok": rec["ollama_binary"]["tar_digest_ok"], "all_blobs_ok": rec["model"]["all_blobs_ok"],
                      "manifest_sha256": rec["model"]["manifest_sha256(copy)"][:12], "renderer": rec["renderer_source_v0.40.6"]["conclusion"][:60]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
