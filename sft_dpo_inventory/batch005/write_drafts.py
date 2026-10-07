# -*- coding: utf-8 -*-
"""batch005 초안 60건을 쓴 스크립트(Claude, 2026-10-07). 질문·초안 gold·근거는 여기 손으로 적은 것이다.

    python sft_dpo_inventory/batch005/write_drafts.py  # -> candidates_draft.yaml
"""
import json, yaml
EV={"trip_count":"trip","fare":"trip","passage_count":"passage","speed":"passage","rpm":"passage","vacant_ratio":"drive"}
def place(pid,text,name,region,od=None):
    c={"id":pid,"text":text,"concept":"LOCATION","subtype":"place","role":"SUBCOND","source":"user","value":{"name":name,"region":region}}
    if od: c["attributes"]={"od_role":od}
    return c
def gold(places,meas,mtext,factors):
    ev=EV.get(meas,"operation")
    cs=list(places)+[{"id":ev,"concept":"EVENT","subtype":ev,"role":"SUPPORT","source":"implicit"},
        {"id":"measure","text":mtext,"concept":"PROPORTION" if meas.endswith("ratio") else "AMOUNT","subtype":meas,"role":"MEASURE","source":"implicit"}]
    return {"concepts":cs,"factors":factors}
C=[]
def add(i,typ,fam,intent,q,why,g): C.append({"id":f"b005-{i:02d}","type":typ,"family":fam,"intent":intent,"question":q,"rationale":why,"gold":g})
A="no_agg_plain"; B="dim_target"; Cc="agg_plain"; D="dim_no_target"; E="agg_dim"
# ---- A: 집계 없음, dimension 없음 (30)
add(1,A,"b005-a-within","b005-a-1","2026년 9월 2일 대구 수성구 안에서 출발해 수성구 안에서 내린 실차 건수는?",
    "출발과 도착이 모두 수성구 안=od_role both(장소 하나). 실차 건수=trip_count. 집계어 없음→aggregation 없음.",
    gold([place("area","수성구","수성구","대구","both")],"trip_count","실차 건수",{"date":"20260902"}))
add(2,A,"b005-a-within","b005-a-1","2026년 9월 2일 출발과 도착이 모두 대구 수성구인 실차 구간은 몇 건이야?",
    "b005-01과 같은 뜻. 출발·도착 모두 한 장소=both.",
    gold([place("area","수성구","수성구","대구","both")],"trip_count","실차 구간은 몇 건",{"date":"20260902"}))
add(3,A,"b005-a-within","b005-a-2","지난주 부산진구 안에서만 오간 택시 실차 건수를 알려줘",
    "안에서만 오간=both. 지난주=last_week. 상위 지역이 발화에 없으므로 region 빈 값.",
    gold([place("area","부산진구","부산진구","","both")],"trip_count","택시 실차 건수",{"date":"last_week"}))
add(4,A,"b005-a-within","b005-a-2","지난주 부산 부산진구 내부에서 승차하고 하차한 실차는 몇 건이었어?",
    "승차·하차 모두 부산진구 내부=both. region 부산.",
    gold([place("area","부산진구","부산진구","부산","both")],"trip_count","실차는 몇 건",{"date":"last_week"}))
add(5,A,"b005-a-within","b005-a-3","2026년 8월 대구 달서구 안에서 오간 개인택시 실차 건수는?",
    "8월=20260801-20260831. 개인택시=taxi_type private. 안에서 오간=both.",
    gold([place("area","달서구","달서구","대구","both")],"trip_count","개인택시 실차 건수",{"date":"20260801-20260831","taxi_type":"private"}))
add(6,A,"b005-a-within","b005-a-3","2026년 8월 한 달간 개인택시가 대구 달서구 안에서 태우고 내린 실차 구간 수는?",
    "b005-05와 같은 뜻. 태우고 내린 곳이 모두 달서구 안=both.",
    gold([place("area","달서구","달서구","대구","both")],"trip_count","실차 구간 수",{"date":"20260801-20260831","taxi_type":"private"}))
add(7,A,"b005-a-within","b005-a-4","2026년 9월 12일 오후 9시부터 11시까지 부산 수영구 안에서 출발·도착한 법인택시 실차 건수는?",
    "시간 210000-230000. 법인택시=corporate. 출발·도착 모두 수영구=both.",
    gold([place("area","수영구","수영구","부산","both")],"trip_count","법인택시 실차 건수",{"date":"20260912","time":"210000-230000","taxi_type":"corporate"}))
add(8,A,"b005-a-within","b005-a-5","이번 달 대구 안에서 출발해 대구 안에서 도착한 실차 건수는?",
    "이번 달=this_month. 시도 단위 장소도 출발·도착 모두 그 안이면 both.",
    gold([place("area","대구","대구","","both")],"trip_count","실차 건수",{"date":"this_month"}))
add(9,A,"b005-a-within","b005-a-6","2026년 7월 1일부터 15일까지 대구 중구 안에서 오간 실차 건수는?",
    "중구는 대구로 지역을 밝혀 동명 구 문제(D4)를 피했다. 안에서 오간=both.",
    gold([place("area","중구","중구","대구","both")],"trip_count","실차 건수",{"date":"20260701-20260715"}))
add(10,A,"b005-a-within","b005-a-7","2026년 9월 19일부터 20일까지 부산 수영구 안에서 출발과 도착이 모두 이뤄진 실차 건수는?",
    "날짜 범위 20260919-20260920. both.",
    gold([place("area","수영구","수영구","부산","both")],"trip_count","실차 건수",{"date":"20260919-20260920"}))
add(11,A,"b005-a-within-vicinity","b005-a-8","2026년 9월 5일 동성로 주변에서 출발해 동성로 주변에서 내린 실차 건수는?",
    "주변→vicinity. 출발·도착 모두 같은 장소 주변=both.",
    gold([place("area","동성로","동성로","","both")],"trip_count","실차 건수",{"date":"20260905","vicinity":True}))
add(12,A,"b005-a-within-vicinity","b005-a-8","2026년 9월 5일 동성로 근처 안에서 시작하고 끝난 실차 구간은 몇 건이야?",
    "b005-11과 같은 뜻. 근처→vicinity, 시작·끝 모두=both.",
    gold([place("area","동성로","동성로","","both")],"trip_count","실차 구간은 몇 건",{"date":"20260905","vicinity":True}))
add(13,A,"b005-a-within-vicinity","b005-a-9","지난달 부산 광안리 부근에서 타고 광안리 부근에서 내린 실차 건수는?",
    "부근→vicinity. 타고 내린 곳 모두 광안리 부근=both. 지난달=last_month.",
    gold([place("area","광안리","광안리","부산","both")],"trip_count","실차 건수",{"date":"last_month","vicinity":True}))
add(14,A,"b005-a-within-vicinity","b005-a-9","지난달 부산 광안리 근처 안에서만 오간 택시 실차는 몇 건이었나요?",
    "b005-13과 같은 뜻.",
    gold([place("area","광안리","광안리","부산","both")],"trip_count","택시 실차는 몇 건",{"date":"last_month","vicinity":True}))
add(15,A,"b005-a-dropoff-vicinity","b005-a-10","2026년 9월 8일 동대구역 근처에 도착한 실차 건수는?",
    "도착=od_role dropoff. 근처→vicinity. 출발지는 말하지 않았으므로 만들지 않는다.",
    gold([place("destination","동대구역","동대구역","","dropoff")],"trip_count","실차 건수",{"date":"20260908","vicinity":True}))
add(16,A,"b005-a-dropoff-vicinity","b005-a-10","2026년 9월 8일 동대구역 주변에서 하차한 실차 구간은 몇 건이야?",
    "b005-15와 같은 뜻. 하차=dropoff.",
    gold([place("destination","동대구역","동대구역","","dropoff")],"trip_count","실차 구간은 몇 건",{"date":"20260908","vicinity":True}))
add(17,A,"b005-a-dropoff-vicinity","b005-a-11","지난주 오전 7시부터 9시까지 대구 신천동 부근에 도착한 실차 건수를 알려줘",
    "시간 070000-090000. 도착=dropoff. 부근→vicinity.",
    gold([place("destination","신천동","신천동","대구","dropoff")],"trip_count","실차 건수",{"date":"last_week","time":"070000-090000","vicinity":True}))
add(18,A,"b005-a-dropoff-vicinity","b005-a-12","2026년 8월 15일 부산 초량동 근처에서 내린 개인택시 실차 건수는?",
    "내린=dropoff. 개인택시=private.",
    gold([place("destination","초량동","초량동","부산","dropoff")],"trip_count","개인택시 실차 건수",{"date":"20260815","taxi_type":"private","vicinity":True}))
add(19,A,"b005-a-dropoff-vicinity","b005-a-12","2026년 8월 15일 부산 초량동 주변이 도착지인 개인택시 실차는 몇 건이야?",
    "b005-18과 같은 뜻. 도착지=dropoff.",
    gold([place("destination","초량동","초량동","부산","dropoff")],"trip_count","개인택시 실차는 몇 건",{"date":"20260815","taxi_type":"private","vicinity":True}))
add(20,A,"b005-a-dropoff-vicinity","b005-a-13","이번 달 대구 두류동 근처에 도착한 법인택시 실차 건수는?",
    "법인택시=corporate. 도착=dropoff. 근처→vicinity.",
    gold([place("destination","두류동","두류동","대구","dropoff")],"trip_count","법인택시 실차 건수",{"date":"this_month","taxi_type":"corporate","vicinity":True}))
add(21,A,"b005-a-rpm-vicinity","b005-a-14","2026년 9월 10일 대구 동성로 근처의 택시 rpm은?",
    "rpm=AMOUNT/rpm(EVENT/passage). 근처→vicinity. 집계어 없음→aggregation 없음. passage는 출발·도착이 없어 od_role 없음.",
    gold([place("place","동성로","동성로","대구")],"rpm","택시 rpm",{"date":"20260910","vicinity":True}))
add(22,A,"b005-a-rpm-vicinity","b005-a-14","2026년 9월 10일 대구 동성로 주변 택시의 분당 회전 속도를 알려줘",
    "b005-21과 같은 뜻. 분당 회전 속도=rpm.",
    gold([place("place","동성로","동성로","대구")],"rpm","분당 회전 속도",{"date":"20260910","vicinity":True}))
add(23,A,"b005-a-rpm-vicinity","b005-a-15","지난주 동대구역 부근을 지난 택시의 rpm은?",
    "부근→vicinity. 지난=통행(passage). rpm.",
    gold([place("place","동대구역","동대구역","")],"rpm","택시의 rpm",{"date":"last_week","vicinity":True}))
add(24,A,"b005-a-rpm-vicinity","b005-a-16","2026년 8월 22일 오후 5시부터 7시까지 부산 광안리 근처 택시 rpm은?",
    "시간 170000-190000. 근처→vicinity.",
    gold([place("place","광안리","광안리","부산")],"rpm","택시 rpm",{"date":"20260822","time":"170000-190000","vicinity":True}))
add(25,A,"b005-a-rpm-vicinity","b005-a-17","이번 달 부산 어린이대공원 주변 개인택시 rpm은 얼마야?",
    "개인택시=private. 주변→vicinity.",
    gold([place("place","어린이대공원","어린이대공원","부산")],"rpm","개인택시 rpm",{"date":"this_month","taxi_type":"private","vicinity":True}))
add(26,A,"b005-a-vacant-vicinity","b005-a-18","2026년 9월 11일 동대구역 근처 택시 공차율은?",
    "공차율=PROPORTION/vacant_ratio(EVENT/drive). 근처→vicinity. 집계어 없음.",
    gold([place("place","동대구역","동대구역","")],"vacant_ratio","택시 공차율",{"date":"20260911","vicinity":True}))
add(27,A,"b005-a-vacant-vicinity","b005-a-18","2026년 9월 11일 동대구역 주변에서 택시가 빈 차로 다닌 비율은?",
    "b005-26과 같은 뜻. 빈 차로 다닌 비율=공차율.",
    gold([place("place","동대구역","동대구역","")],"vacant_ratio","빈 차로 다닌 비율",{"date":"20260911","vicinity":True}))
add(28,A,"b005-a-vacant-vicinity","b005-a-19","지난달 대구 동성로 부근 법인택시 공차율은?",
    "법인택시=corporate. 부근→vicinity.",
    gold([place("place","동성로","동성로","대구")],"vacant_ratio","법인택시 공차율",{"date":"last_month","taxi_type":"corporate","vicinity":True}))
add(29,A,"b005-a-vacant-vicinity","b005-a-20","2026년 8월 3일 오전 10시부터 정오까지 부산 광안리 근처 택시 공차율을 알려줘",
    "시간 100000-120000(정오=12시). 근처→vicinity.",
    gold([place("place","광안리","광안리","부산")],"vacant_ratio","택시 공차율",{"date":"20260803","time":"100000-120000","vicinity":True}))
add(30,A,"b005-a-vacant-vicinity","b005-a-21","지난주 대구 두류동 주변 개인택시 공차율은 얼마였어?",
    "개인택시=private. 주변→vicinity.",
    gold([place("place","두류동","두류동","대구")],"vacant_ratio","개인택시 공차율",{"date":"last_week","taxi_type":"private","vicinity":True}))
# ---- B: 집계 없음, dimension + dimension_target (15)
add(31,B,"b005-b-within-by-end","b005-b-1","2026년 9월 대구 수성구 안에서 오간 실차를 도착 읍면동별로 세어줘",
    "안에서 오간=od_role both(장소가 제한하는 끝). 도착 읍면동별=dimension emd, dimension_target dropoff(묶는 끝). 둘은 독립.",
    gold([place("area","수성구","수성구","대구","both")],"trip_count","실차",{"date":"20260901-20260930","dimension":"emd","dimension_target":"dropoff"}))
add(32,B,"b005-b-within-by-end","b005-b-2","2026년 9월 대구 수성구 안에서 출발·도착한 실차 가운데 도착 건수가 가장 많은 읍면동 세 곳은?",
    "b005-31에 순위(top 3)를 더했다. 도착 건수 기준 읍면동=dimension_target dropoff.",
    gold([place("area","수성구","수성구","대구","both")],"trip_count","도착 건수",{"date":"20260901-20260930","dimension":"emd","dimension_target":"dropoff","order":"top","limit":3}))
add(33,B,"b005-b-dropoff-by-pickup","b005-b-3","지난주 동대구역에 도착한 실차를 출발 읍면동별로 보여줘",
    "동대구역 od_role dropoff, 묶는 끝은 출발(dimension_target pickup).",
    gold([place("destination","동대구역","동대구역","","dropoff")],"trip_count","실차",{"date":"last_week","dimension":"emd","dimension_target":"pickup"}))
add(34,B,"b005-b-dropoff-by-pickup","b005-b-3","지난주 동대구역이 도착지인 실차 구간을 승차 읍면동 기준으로 나눠서 세어줘",
    "b005-33과 같은 뜻. 승차 읍면동 기준=dimension_target pickup.",
    gold([place("destination","동대구역","동대구역","","dropoff")],"trip_count","실차 구간",{"date":"last_week","dimension":"emd","dimension_target":"pickup"}))
add(35,B,"b005-b-pickup-by-route","b005-b-4","2026년 8월 대구 동성로에서 출발한 실차를 읍면동 출발지-도착지 조합별로 세어줘",
    "동성로 od_role pickup. 출발지-도착지 조합=dimension_target both(명시). od_role both와 뜻이 다르다.",
    gold([place("origin","동성로","동성로","대구","pickup")],"trip_count","실차",{"date":"20260801-20260831","dimension":"emd","dimension_target":"both"}))
add(36,B,"b005-b-pickup-by-route","b005-b-4","2026년 8월 동성로에서 승차한 실차 건수를 승하차 읍면동 노선별로 알려줘",
    "b005-35와 같은 뜻. 승하차 노선=dimension_target both. 지역이 발화에 없어 region 빈 값.",
    gold([place("origin","동성로","동성로","","pickup")],"trip_count","실차 건수",{"date":"20260801-20260831","dimension":"emd","dimension_target":"both"}))
add(37,B,"b005-b-no-place-route","b005-b-5","2026년 9월 1일부터 14일까지 시군구 출발지-도착지 조합별 실차 건수를 보여줘",
    "장소 없음. 시군구 조합=dimension sigungu, dimension_target both. 순위어 없음→order 없음.",
    gold([],"trip_count","실차 건수",{"date":"20260901-20260914","dimension":"sigungu","dimension_target":"both"}))
add(38,B,"b005-b-within-by-end","b005-b-6","지난달 부산 부산진구 안에서 오간 실차를 도착 읍면동별로 셀 때 가장 적은 두 곳은?",
    "od_role both, dimension_target dropoff, 가장 적은 두 곳=bottom 2.",
    gold([place("area","부산진구","부산진구","부산","both")],"trip_count","실차",{"date":"last_month","dimension":"emd","dimension_target":"dropoff","order":"bottom","limit":2}))
add(39,B,"b005-b-within-by-end","b005-b-7","2026년 9월 대구 달서구 안에서 출발과 도착이 모두 이뤄진 실차를 출발 읍면동별로 세어줘",
    "od_role both, 출발 읍면동별=dimension_target pickup.",
    gold([place("area","달서구","달서구","대구","both")],"trip_count","실차",{"date":"20260901-20260930","dimension":"emd","dimension_target":"pickup"}))
add(40,B,"b005-b-no-place-end","b005-b-8","2026년 9월 22일 읍면동별 실차 하차 건수를 알려줘",
    "장소 없음. 하차 기준 읍면동=dimension_target dropoff.",
    gold([],"trip_count","실차 하차 건수",{"date":"20260922","dimension":"emd","dimension_target":"dropoff"}))
add(41,B,"b005-b-no-place-end","b005-b-9","2026년 9월 22일 승차 읍면동별 실차 건수는?",
    "b005-40과 묶는 끝만 다르다(pickup).",
    gold([],"trip_count","실차 건수",{"date":"20260922","dimension":"emd","dimension_target":"pickup"}))
add(42,B,"b005-b-within-by-end","b005-b-10","이번 달 대구 안에서 오간 실차를 도착 시군구별로 세어줘",
    "대구 od_role both, 도착 시군구별=dimension sigungu, dimension_target dropoff.",
    gold([place("area","대구","대구","","both")],"trip_count","실차",{"date":"this_month","dimension":"sigungu","dimension_target":"dropoff"}))
add(43,B,"b005-b-od-pair-route","b005-b-11","2026년 8월 대구에서 출발해 부산에 도착한 실차를 출발·도착 시군구 조합별로 세어줘",
    "대구 pickup, 부산 dropoff(장소 두 개). 시군구 조합=dimension_target both.",
    gold([place("origin","대구","대구","","pickup"),place("destination","부산","부산","","dropoff")],"trip_count","실차",{"date":"20260801-20260831","dimension":"sigungu","dimension_target":"both"}))
add(44,B,"b005-b-no-place-end","b005-b-12","지난주 법인택시의 시군구별 승차 실차 건수를 보여줘",
    "장소 없음. 법인택시=corporate. 승차 시군구별=dimension_target pickup.",
    gold([],"trip_count","승차 실차 건수",{"date":"last_week","taxi_type":"corporate","dimension":"sigungu","dimension_target":"pickup"}))
add(45,B,"b005-b-dropoff-by-pickup","b005-b-13","2026년 7월 부산 부산진구에 도착한 실차를 출발 시군구별로 세어줘",
    "부산진구 od_role dropoff, 출발 시군구별=dimension sigungu, dimension_target pickup.",
    gold([place("destination","부산진구","부산진구","부산","dropoff")],"trip_count","실차",{"date":"20260701-20260731","dimension":"sigungu","dimension_target":"pickup"}))
# ---- C: 집계 있음, dimension 없음 (7)
add(46,Cc,"b005-c-vacant-vicinity-agg","b005-c-1","2026년 9월 15일 동대구역 근처 택시 공차율의 평균은?",
    "평균=aggregation avg. 근처→vicinity.",
    gold([place("place","동대구역","동대구역","")],"vacant_ratio","택시 공차율",{"date":"20260915","vicinity":True,"aggregation":"avg"}))
add(47,Cc,"b005-c-vacant-vicinity-agg","b005-c-1","2026년 9월 15일 동대구역 주변 택시 공차율을 평균 내면 얼마야?",
    "b005-46과 같은 뜻.",
    gold([place("place","동대구역","동대구역","")],"vacant_ratio","택시 공차율",{"date":"20260915","vicinity":True,"aggregation":"avg"}))
add(48,Cc,"b005-c-vacant-vicinity-agg","b005-c-2","지난주 부산 광안리 주변 택시 공차율 최댓값은?",
    "최댓값=aggregation max. 주변→vicinity.",
    gold([place("place","광안리","광안리","부산")],"vacant_ratio","택시 공차율",{"date":"last_week","vicinity":True,"aggregation":"max"}))
add(49,Cc,"b005-c-rpm-vicinity-agg","b005-c-3","2026년 8월 20일 오후 6시부터 8시까지 대구 동성로 부근 택시 rpm 평균은?",
    "시간 180000-200000. 평균=avg. 부근→vicinity.",
    gold([place("place","동성로","동성로","대구")],"rpm","택시 rpm",{"date":"20260820","time":"180000-200000","vicinity":True,"aggregation":"avg"}))
add(50,Cc,"b005-c-rpm-vicinity-agg","b005-c-3","2026년 8월 20일 18시에서 20시 사이 대구 동성로 근처를 지난 택시들의 분당 회전 속도 평균을 알려줘",
    "b005-49와 같은 뜻.",
    gold([place("place","동성로","동성로","대구")],"rpm","분당 회전 속도",{"date":"20260820","time":"180000-200000","vicinity":True,"aggregation":"avg"}))
add(51,Cc,"b005-c-ratio-min","b005-c-4","지난달 부산 수영구 택시 가동률의 최솟값은?",
    "가동률=PROPORTION/active_taxi_ratio(EVENT/operation). 최솟값=min. 근처 표현 없음.",
    gold([place("place","수영구","수영구","부산")],"active_taxi_ratio","택시 가동률",{"date":"last_month","aggregation":"min"}))
add(52,Cc,"b005-c-ratio-med","b005-c-5","2026년 8월 개인택시 가동률의 중간값은?",
    "장소 없음. 중간값=med. 개인택시=private.",
    gold([],"active_taxi_ratio","개인택시 가동률",{"date":"20260801-20260831","taxi_type":"private","aggregation":"med"}))
# ---- D: 집계 없음, dimension 있음, dimension_target 없음 (5)
add(53,D,"b005-d-passage-sigungu","b005-d-1","2026년 9월 4일 대구의 시군구별 택시 통행량을 알려줘",
    "통행량=passage_count. 시군구별=dimension sigungu. passage에는 묶는 끝(dimension_target)이 없다. 순위어 없음.",
    gold([place("place","대구","대구","")],"passage_count","택시 통행량",{"date":"20260904","dimension":"sigungu"}))
add(54,D,"b005-d-passage-sigungu","b005-d-2","지난주 부산의 시군구별 공차 택시 통행량은?",
    "공차 택시 통행량=passage_count + taxi_status vacant. 시군구별=sigungu.",
    gold([place("place","부산","부산","")],"passage_count","공차 택시 통행량",{"date":"last_week","taxi_status":"vacant","dimension":"sigungu"}))
add(55,D,"b005-d-passage-h3","b005-d-3","2026년 9월 9일 대구 동성로의 H3 셀별 택시 통행량은?",
    "H3 셀별=dimension h3. 근처 표현 없음→vicinity 없음.",
    gold([place("place","동성로","동성로","대구")],"passage_count","택시 통행량",{"date":"20260909","dimension":"h3"}))
add(56,D,"b005-d-passage-h3-vicinity","b005-d-4","2026년 9월 24일 동대구역 근처 H3 셀별 통행량을 보여줘",
    "근처→vicinity. H3 셀별=h3.",
    gold([place("place","동대구역","동대구역","")],"passage_count","통행량",{"date":"20260924","vicinity":True,"dimension":"h3"}))
add(57,D,"b005-d-passage-h3-vicinity","b005-d-5","2026년 8월 9일 오후 2시부터 4시까지 부산 광안리 주변의 H3 셀별 택시 통행량은?",
    "시간 140000-160000. 주변→vicinity. H3 셀별=h3.",
    gold([place("place","광안리","광안리","부산")],"passage_count","택시 통행량",{"date":"20260809","time":"140000-160000","vicinity":True,"dimension":"h3"}))
# ---- E: 집계 있음, dimension 있음 (3)
add(58,E,"b005-e-revenue-sido-med","b005-e-1","지난달 택시 하루 수입의 중간값이 가장 높은 시도 세 곳은?",
    "수입=revenue. 중간값=med. 시도별 순위=dimension sido, top 3. 요일 순위(D1)가 아니다.",
    gold([],"revenue","택시 하루 수입",{"date":"last_month","aggregation":"med","dimension":"sido","order":"top","limit":3}))
add(59,E,"b005-e-ratio-sido-min","b005-e-2","2026년 8월 시도별 택시 가동률 최솟값이 가장 낮은 두 곳은?",
    "가동률 최솟값=active_taxi_ratio min. 가장 낮은 두 곳=bottom 2.",
    gold([],"active_taxi_ratio","택시 가동률",{"date":"20260801-20260831","aggregation":"min","dimension":"sido","order":"bottom","limit":2}))
add(60,E,"b005-e-ratio-dow-max","b005-e-3","지난달 요일별 택시 가동률 최댓값이 가장 높은 요일은?",
    "요일별=dimension dayofweek. 최댓값=max. 가장 높은 요일 하나=top 1.",
    gold([],"active_taxi_ratio","택시 가동률",{"date":"last_month","aggregation":"max","dimension":"dayofweek","order":"top","limit":1}))
assert len(C)==60
header="""# batch005 annotation 후보 초안. Claude가 2026-10-07에 새로 썼다. 사람 검토 전이며 승인이 아니다(결정 45).
# - 배분: pilot_prep_004/type_target(결정 40-C)의 칸별 배분을 따랐다. 칸 안 세부는 보호 셋 family와 겹치지 않는 범위에서 골랐다(README 2절).
# - 보호된 셋(evaluation/ 아래 질문과 그 부모, 업체 100, root의 질문·stub 파일, 새 선택용·보조 시험 후보)의 문장을 보거나 바꿔 쓰지 않았다.
#   family 겹침을 피하려고 보호 셋 정답의 라벨 조합(측정값·od_role·집계·묶음 구조)만 썼다. 문장은 현재 planner prompt(87048d0c)의 계약 설명을 따랐다.
# - D1–D4(evaluation/real_data/decisions.md)에 걸리는 질문(수입 기준 요일 순위, 운행일 지표, 기간 활성 택시 수, 지역 없는 동명 구)은 만들지 않았다.
# - 기준일: 2026-09-25(평가 harness와 같다).
# - type: 유형 칸(no_agg_plain=집계·묶음 없음, dim_target=dimension+dimension_target, agg_plain=집계만, dim_no_target=dimension만,
#   agg_dim=집계+dimension). family: 의미 family(대조 묶음), intent: 같은 뜻의 표현 묶음.
"""
body=yaml.safe_dump({"reference_date":"2026-09-25","candidates":C},allow_unicode=True,sort_keys=False,width=200,default_flow_style=None)
open(__import__("pathlib").Path(__file__).resolve().parent / "candidates_draft.yaml", "w", encoding="utf-8").write(header+body)
print("ok")
