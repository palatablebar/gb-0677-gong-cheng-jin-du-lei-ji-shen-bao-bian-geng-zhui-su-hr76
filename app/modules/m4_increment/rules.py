from app.values import number
from app.reasons import reject,party_of,claim_key
from app.errors import DomainError
def previous_for(overrides,row,shared_numbers):
    """前审批复：优先「分包商|编号」精确键；裸编号仅在该编号不跨方共号时生效，避免把一家的更正套到另一家。"""
    exact=overrides.get(claim_key(row))
    if exact is not None: return exact
    claim=row["claim_id"]
    if claim in shared_numbers: return row["previous_qty"]
    return overrides.get(claim,row["previous_qty"])
def evaluate(rows,context):
    good=[];bad=[];overrides=context.get("parameters",{}).get("previous_revisions",{});seen={}
    parties_by_number={}
    for row in rows: parties_by_number.setdefault(row["claim_id"],set()).add(party_of(row))
    shared_numbers={k for k,v in parties_by_number.items() if len(v)>1}
    for row in sorted(rows,key=lambda x:(party_of(x),x["item"],x["period"],x["claim_id"],x.get("_line",0))):
        # 同号不同分包商是两个独立申报，不能按清单+周期去重掉其中一方。
        key=(party_of(row),row["item"],row["period"])
        if key in seen:
            bad.append(reject(row,"DUPLICATE_PERIOD","同分包商同清单同周期重复申报，已保留首条"))
            continue
        seen[key]=row
        prev=number(previous_for(overrides,row,shared_numbers));current=number(row["cumulative_qty"])
        if prev<0:raise DomainError("BAD_PREVIOUS","前审累计量不能为负")
        incremental=current-prev
        if incremental<0 and row.get("reversal")!="approved":bad.append(reject(row,"REVERSAL_REQUIRED","负进度缺少已批冲回凭证"));continue
        good.append({**row,"approved_previous":str(prev),"increment_qty":str(incremental),"gross_amount":str(incremental*number(row["unit_price"]))})
    return {"rows":good,"quarantine":bad,"metrics":{"accepted":len(good),"negative_claims":sum(number(r["increment_qty"])<0 for r in good),"parties":len({party_of(r) for r in good})}}
