"""Read-only diagnostics and real CUDA operations; optional extensions are opt-in."""
import argparse
import importlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
from pathlib import Path


def command(argv, timeout=8):
    if not shutil.which(argv[0]):
        return {"status": "NOT INSTALLED"}
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {"status": "PASS" if p.returncode == 0 else "FAIL", "output": (p.stdout + p.stderr).strip()}
    except subprocess.TimeoutExpired as exc:
        # tegrastats streams until stopped; subprocess.run kills only our query process.
        output = exc.stdout or b''
        if isinstance(output, bytes):
            output = output.decode(errors='replace')
        return {'status': 'PASS' if output else 'FAIL', 'output': output.strip(), 'bounded_query': True}
    except OSError as exc:
        return {"status": "FAIL", "error": str(exc)}


def system_memory():
    try:
        values = {line.split(':')[0]: int(line.split()[1]) * 1024
                  for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:', 'MemAvailable:'))}
        return {"total_bytes": values['MemTotal'], "available_bytes": values['MemAvailable']}
    except (OSError, ValueError, KeyError):
        return {"total_bytes": None, "available_bytes": None}


def temperatures():
    result = {}
    for directory in Path('/sys/class/thermal').glob('thermal_zone*'):
        try:
            result[(directory / 'type').read_text().strip()] = int((directory / 'temp').read_text()) / 1000
        except (OSError, ValueError, TypeError, UnicodeError):
            pass
    return result


def cuda_tests(torch, optional=False):
    results = {name: {"status": "NOT TESTED"} for name in ('bf16', 'sdpa', 'bitsandbytes', 'qlora', 'flash_attn')}
    if not torch.cuda.is_available():
        for key in ('bf16', 'sdpa'):
            results[key] = {"status": "FAIL", "error": "CUDA unavailable"}
        return results
    def run(name, operation):
        try:
            operation()
            torch.cuda.synchronize()
            results[name] = {"status": "PASS"}
        except Exception as exc:
            results[name] = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
    def bf16():
        x = torch.randn(64, 64, device='cuda', dtype=torch.bfloat16, requires_grad=True)
        y = x @ x.T
        y.float().square().mean().backward()
        if not torch.isfinite(y).all() or not torch.isfinite(x.grad).all():
            raise RuntimeError('Nonfinite BF16 result or gradient')
    def sdpa():
        q = torch.randn(1, 2, 64, 64, device='cuda', dtype=torch.bfloat16, requires_grad=True)
        y = torch.nn.functional.scaled_dot_product_attention(q, q, q, is_causal=True)
        y.float().square().mean().backward()
        if not torch.isfinite(q.grad).all():
            raise RuntimeError('Nonfinite SDPA gradient')
    run('bf16', bf16)
    run('sdpa', sdpa)
    if optional:
        def quant():
            bnb = importlib.import_module('bitsandbytes')
            x = torch.randn(64, 64, device='cuda', dtype=torch.bfloat16)
            packed, state = bnb.functional.quantize_4bit(x, quant_type='nf4')
            restored = bnb.functional.dequantize_4bit(packed, state)
            if not torch.isfinite(restored).all():
                raise RuntimeError('Nonfinite NF4 result')
        run('bitsandbytes', quant)
        def qlora():
            bnb = importlib.import_module('bitsandbytes')
            layer = bnb.nn.Linear4bit(64, 64, bias=False, compute_dtype=torch.bfloat16,
                                     quant_type='nf4').cuda()
            x = torch.randn(2, 64, device='cuda', dtype=torch.bfloat16, requires_grad=True)
            layer(x).float().square().mean().backward()
            if not torch.isfinite(x.grad).all():
                raise RuntimeError('Nonfinite 4-bit linear gradient')
        run('qlora', qlora)
        def flash():
            module = importlib.import_module('flash_attn')
            q = torch.randn(1, 64, 2, 64, device='cuda', dtype=torch.bfloat16, requires_grad=True)
            module.flash_attn_func(q, q, q, causal=True).float().square().mean().backward()
        run('flash_attn', flash)
    return results


def diagnose(optional=False):
    deps = {}
    for package in ('torch', 'transformers', 'trl', 'peft', 'accelerate', 'bitsandbytes', 'flash_attn'):
        try:
            version = importlib.metadata.version(package)
            module = importlib.import_module(package)
            deps[package] = {"version": version, "import": "PASS"}
        except importlib.metadata.PackageNotFoundError:
            deps[package] = {"status": "NOT INSTALLED"}
        except Exception as exc:
            deps[package] = {"version": version, "import": "FAIL", "error": str(exc)}
    report = {"system": {"uname": platform.uname()._asdict(), "architecture": platform.machine(),
              "python": platform.python_version(), "os": command(['lsb_release', '-a']),
              "jetpack": command(['dpkg-query', '-W', 'nvidia-jetpack', 'nvidia-l4t-core']),
              "nvcc": command(['nvcc', '--version']), "memory": system_memory()},
              "dependencies": deps, "nvidia_smi": command(['nvidia-smi']),
              "power_mode": command(['nvpmodel', '-q']),
              "clocks": command(['jetson_clocks', '--show']),
              "tegrastats": command(['tegrastats', '--interval', '1000'], timeout=2),
              "temperature_c": temperatures()}
    try:
        torch = importlib.import_module('torch')
        report['torch'] = {"version": torch.__version__, "cuda_runtime": torch.version.cuda,
                           "cuda_available": torch.cuda.is_available()}
        if torch.cuda.is_available():
            report['gpu'] = {"name": torch.cuda.get_device_name(),
                             "capability": list(torch.cuda.get_device_capability()),
                             "cuda_reported_total_bytes": torch.cuda.get_device_properties(0).total_memory}
        report['compatibility'] = cuda_tests(torch, optional)
    except Exception as exc:
        report['torch'] = {"error": str(exc)}
        report['compatibility'] = {key: {"status": "NOT TESTED"} for key in ('bf16', 'sdpa', 'bitsandbytes', 'qlora', 'flash_attn')}
    if deps['flash_attn'].get('status') == 'NOT INSTALLED':
        report['compatibility']['flash_attn'] = {"status": "NOT INSTALLED"}
    ready = all(report['compatibility'][key]['status'] == 'PASS' for key in ('bf16', 'sdpa'))
    ready = ready and all(deps[key].get('import') == 'PASS' for key in ('transformers', 'trl', 'peft', 'accelerate'))
    report['bf16_lora'] = 'PASS' if ready else 'FAIL'
    report['recommendation'] = 'thor_bf16_lora; run tokenizer analysis then smoke training' if ready else 'Fix the reported environment failures before training'
    report['notes'] = ['CUDA allocation shares system memory on Thor; preserve MemAvailable reserve.',
                       'Operation PASS is compatibility evidence, not full training validation.',
                       'Power and clock settings were queried only; permission failures are diagnostic.']
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-optional', action='store_true', help='Run NF4/4-bit backward and FlashAttention CUDA tests if installed')
    parser.add_argument('--output', help='Save machine-readable diagnostics JSON')
    args = parser.parse_args(argv)
    report = diagnose(args.test_optional)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
