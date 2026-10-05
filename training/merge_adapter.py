"""Export a LoRA policy as a full Hugging Face checkpoint (no quantized merge)."""
import argparse
import shutil
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dtype", choices=["float32", "float16", "bfloat16"], default="bfloat16")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if Path(args.output).resolve() in {Path(args.base).resolve(), Path(args.adapter).resolve()}:
        parser.error("Output must differ from base and adapter")
    if args.dry_run:
        print(f"Merge {args.base} + {args.adapter} -> {args.output} ({args.dtype})")
        return
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    base = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=getattr(torch, args.dtype), device_map="cpu")
    merged = PeftModel.from_pretrained(base, args.adapter).merge_and_unload()
    merged.save_pretrained(args.output, safe_serialization=True)
    AutoTokenizer.from_pretrained(args.base).save_pretrained(args.output)
    provenance = Path(args.adapter) / "training_provenance.json"
    if provenance.exists():
        shutil.copy2(provenance, Path(args.output) / provenance.name)


if __name__ == "__main__":
    main()
