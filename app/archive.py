import csv,io,json
HEADER=["run_id","input_sha256","rule_version","kind","party","claim_id","receipt_no","source_lines","reason","evidence"]
def build_archive(run):
    stream=io.StringIO(newline="");writer=csv.writer(stream)
    writer.writerow(HEADER)
    meta=run["manifest"]
    stages=run.get("stages") or []
    for row in stages[-1]["rows"]:
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"accepted",row.get("party",""),row.get("claim_id",""),
                         row.get("receipt_no",""),json.dumps(row.get("_sources",[])),row.get("status",""),json.dumps(row,ensure_ascii=False)])
    for row in stages[-1].get("cumulative_quarantine",[]):
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"quarantine",row.get("party",""),row.get("claim_id",""),
                         row.get("receipt_no",""),json.dumps(row.get("_sources",[])),row.get("reason",""),json.dumps(row,ensure_ascii=False)])
    for item in run.get("collisions",[]):
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"shared_number","|".join(item.get("parties",[])),item.get("claim_id",""),
                         "|".join(x.get("receipt_no","") for x in item.get("receipts",[])),json.dumps([x.get("line") for x in item.get("receipts",[])]),
                         "SAME_NUMBER_ACROSS_PARTIES",json.dumps(item,ensure_ascii=False)])
    for item in run.get("adjudications",[]):
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"conflict_basis",item.get("party",""),item.get("claim_id",""),
                         item.get("rejected",{}).get("receipt_no",""),json.dumps([item.get("kept",{}).get("line"),item.get("rejected",{}).get("line")]),
                         item.get("conflict_id",""),json.dumps(item,ensure_ascii=False)])
    return "﻿"+stream.getvalue()
