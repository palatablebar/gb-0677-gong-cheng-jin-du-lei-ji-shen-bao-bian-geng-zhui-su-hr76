from decimal import Decimal
from app.reasons import sources,party_of
from app.errors import DomainError
def evaluate(rows,context):
    intake=context.get("intake")
    bad=context.get("quarantine",[])
    accepted=set(x for row in rows for x in sources(row))
    rejected=set(x for row in bad for x in sources(row))
    if accepted & rejected: raise DomainError("LINEAGE_OVERLAP","同一来源行被重复裁决")
    m={"accepted_inputs":len(accepted),"quarantine_inputs":len(rejected),"output_records":len(rows)}
    if intake:
        excluded=intake["duplicate"]+intake["blank"]+intake["repeated_headers"]
        m.update(input=intake["input"],excluded=excluded,balanced=intake["input"]==len(accepted)+len(rejected)+excluded)
    else:m.update(input=len(accepted)+len(rejected),excluded=0,balanced=True)
    output=[]
    for row in rows:
        expected=Decimal(str(row.get("expected","0")));reported=Decimal(str(row.get("reported","0")))
        output.append({**row,"difference":str(expected-reported),"status":"通过" if expected==reported else "差异"})
    # 按分包商分别汇总：同号两方各自计量，签证合计为两方之和。
    parties={}
    for row in output:
        p=parties.setdefault(party_of(row),{"records":0,"expected_total":Decimal(0),"reported_total":Decimal(0),"differences":0})
        p["records"]+=1;p["expected_total"]+=Decimal(str(row.get("expected","0")));p["reported_total"]+=Decimal(str(row.get("reported","0")))
        p["differences"]+=row["status"]=="差异"
    m.update(expected_total=str(sum((Decimal(str(r.get("expected","0"))) for r in rows),Decimal(0))),
             reported_total=str(sum((Decimal(str(r.get("reported","0"))) for r in rows),Decimal(0))),
             differences=sum(r["status"]=="差异" for r in output),
             parties={k:{"records":v["records"],"expected_total":str(v["expected_total"]),"reported_total":str(v["reported_total"]),"differences":v["differences"]} for k,v in sorted(parties.items())})
    return {"rows":output,"quarantine":[],"metrics":m}
