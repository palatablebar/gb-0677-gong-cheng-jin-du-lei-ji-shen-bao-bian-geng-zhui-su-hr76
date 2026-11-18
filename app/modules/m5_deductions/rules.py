from decimal import Decimal
from app.values import number,money
from app.reasons import party_of
from app.errors import DomainError
def evaluate(rows,context):
    p=context.get("parameters",{});retention=number(p.get("retention_rate","0.05"));advance=number(p.get("advance_rate","0.10"))
    if not Decimal(0)<=retention<=1 or not Decimal(0)<=advance<=1 or retention+advance>1:raise DomainError("BAD_DEDUCTION","扣回比例无效")
    good=[]
    for row in rows:
        gross=number(row["gross_amount"]);ret=number(money(gross*retention));adv=number(money(gross*advance));net=gross-ret-adv
        good.append({**row,"retention":money(ret),"advance_recovery":money(adv),"expected":money(net)})
    parties={}
    for row in good:
        p=parties.setdefault(party_of(row),{"records":0,"gross_total":Decimal(0),"net_total":Decimal(0)})
        p["records"]+=1;p["gross_total"]+=number(row["gross_amount"]);p["net_total"]+=number(row["expected"])
    return {"rows":good,"quarantine":[],"metrics":{"gross_total":money(sum((number(r["gross_amount"]) for r in rows),Decimal(0))),
            "net_total":money(sum((number(r["expected"]) for r in good),Decimal(0))),
            "parties":{k:{"records":v["records"],"gross_total":money(v["gross_total"]),"net_total":money(v["net_total"])} for k,v in sorted(parties.items())}}}
