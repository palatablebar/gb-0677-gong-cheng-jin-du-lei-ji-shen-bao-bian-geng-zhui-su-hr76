import hashlib,json
from decimal import Decimal
from app.errors import DomainError
from app.reasons import sources,party_of,claim_key
def evaluate(rows,context):
    stages=[v for v in context.values() if isinstance(v,dict) and "metrics" in v]
    balances=[s["metrics"]["balanced"] for s in stages if "balanced" in s["metrics"]]
    if balances and not all(balances): raise DomainError("UNBALANCED","来源行未对平，不能归档")
    keys=[claim_key(r) for r in rows]
    if len(keys)!=len(set(keys)): raise DomainError("ARCHIVE_DUPLICATE","归档业务键重复")
    # 同号但不同分包商是合法共号，单独登记，不阻断归档。
    shared={}
    for row in rows: shared.setdefault(str(row.get("claim_id","")),set()).add(party_of(row))
    collisions=[{"claim_id":k,"parties":sorted(v)} for k,v in sorted(shared.items()) if len(v)>1]
    # 按分包商合计，使签证与累计、扣回环环相扣。
    parties={}
    for row in rows:
        p=parties.setdefault(party_of(row),{"records":0,"gross_total":Decimal(0),"expected_total":Decimal(0),"reported_total":Decimal(0)})
        p["records"]+=1
        p["gross_total"]+=Decimal(str(row.get("gross_amount","0")))
        p["expected_total"]+=Decimal(str(row.get("expected","0")))
        p["reported_total"]+=Decimal(str(row.get("reported","0")))
    encoded=json.dumps(rows,ensure_ascii=False,sort_keys=True,default=str).encode()
    return {"rows":rows,"quarantine":[],"collisions":collisions,"metrics":{"records":len(rows),"source_lines":len(set(x for row in rows for x in sources(row))),
            "parties":{k:{"records":v["records"],"gross_total":str(v["gross_total"]),"expected_total":str(v["expected_total"]),"reported_total":str(v["reported_total"])} for k,v in sorted(parties.items())},
            "party_count":len(parties),"shared_numbers":len(collisions),
            "gross_total":str(sum((Decimal(str(r.get("gross_amount","0"))) for r in rows),Decimal(0))),
            "expected_total":str(sum((Decimal(str(r.get("expected","0"))) for r in rows),Decimal(0))),
            "sha256":hashlib.sha256(encoded).hexdigest(),"ready":True,"differences":sum(r.get("status")=="差异" for r in rows)}}
