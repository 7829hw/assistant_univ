"""한 문항의 계획 요청을 같은 설정(temperature 0, think 미지정)으로 보내 thinking 원문을 저장한다. 원인 진단용."""
import json, sys, time, httpx
sys.path.insert(0, sys.argv[1])
from geoflow.planner import GeoFlowPlanner
sp = GeoFlowPlanner(client=None).system_prompt()
H = 'http://localhost:11434'
model = sys.argv[2]
out = []
for q in sys.argv[3:]:
    for m in httpx.get(H + '/api/ps').json()['models']:
        httpx.post(H + '/api/generate', json={'model': m['name'], 'keep_alive': 0}, timeout=60)
    r = httpx.post(H + '/api/chat', json={'model': model, 'messages': [{'role': 'system', 'content': sp},
                   {'role': 'user', 'content': q}], 'stream': False, 'options': {'temperature': 0}}, timeout=300).json()
    out.append({'question': q, 'thinking': r['message'].get('thinking'), 'content': r['message'].get('content')})
    print(json.dumps(out[-1], ensure_ascii=False), flush=True)
