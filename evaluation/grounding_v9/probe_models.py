"""설치 모델마다 production system prompt로 계획 요청 하나를 보내 속도·context·VRAM·thinking을 본다(정확도 아님)."""
import json, sys, time
import httpx
from geoflow.planner import GeoFlowPlanner

sp = GeoFlowPlanner(client=None).system_prompt()
H = 'http://localhost:11434'
models = sys.argv[1].split(',')
questions = sys.argv[2:] or ['지난달 대구 수성구에서 출발한 실차를 하차 읍면동별로 셌을 때 가장 많은 두 곳은?']


def unload():
    for mm in httpx.get(H + '/api/ps').json()['models']:
        httpx.post(H + '/api/generate', json={'model': mm['name'], 'keep_alive': 0}, timeout=60)


for m in models:
    for q in questions:
        unload()
        t = time.time()
        rec = {'model': m, 'question': q[:30]}
        try:
            r = httpx.post(H + '/api/chat', json={'model': m, 'messages': [
                {'role': 'system', 'content': sp}, {'role': 'user', 'content': q}],
                'stream': False, 'options': {'temperature': 0}}, timeout=300).json()
            msg = r.get('message', {})
            rec.update({'load_s': round(r.get('load_duration', 0) / 1e9, 1),
                        'prompt_tokens': r.get('prompt_eval_count'), 'eval_tokens': r.get('eval_count'),
                        'done_reason': r.get('done_reason'),
                        'eval_tok_per_s': round(r.get('eval_count', 0) / max(r.get('eval_duration', 1) / 1e9, 1e-9), 1),
                        'thinking_chars': len(msg.get('thinking') or ''),
                        'content': (msg.get('content') or '')[:600].replace('\n', ' ')})
        except Exception as e:  # noqa: BLE001
            rec['error'] = type(e).__name__
        rec['wall_s'] = round(time.time() - t, 1)
        ps = [x for x in httpx.get(H + '/api/ps').json()['models'] if x['name'] == m]
        if ps:
            rec.update({'ctx': ps[0].get('context_length'), 'vram_GiB': round(ps[0]['size_vram'] / 2**30, 1),
                        'size_GiB': round(ps[0]['size'] / 2**30, 1)})
        print(json.dumps(rec, ensure_ascii=False), flush=True)
unload()
