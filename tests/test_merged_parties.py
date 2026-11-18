import csv,io
from decimal import Decimal
import pytest
from app.pipeline import calculate,load_sample,execute
from app import store

# 两家分包商各自从 00001 起编，本月合并导入。


@pytest.fixture
def merged(): return calculate(load_sample("merged.csv"))


def test_same_number_both_parties_survive(merged):
    rows=merged["stages"][0]["rows"]
    survivors={(r["party"],r["claim_id"]) for r in rows}
    assert ("华建","00001") in survivors and ("永固","00001") in survivors
    assert ("华建","00002") in survivors and ("永固","00002") in survivors


def test_same_number_is_not_a_duplicate(merged):
    m=merged["stages"][0]["metrics"]
    assert m["duplicate"]==0
    assert not any(q["reason"]=="DUPLICATE_CONFLICT" for q in merged["stages"][0]["quarantine"] if q["claim_id"] in {"00001","00002"})


def test_shared_numbers_are_recorded_with_basis(merged):
    shared={c["claim_id"]:c for c in merged["collisions"]}
    assert set(shared)=={"00001","00002"}
    assert shared["00001"]["parties"]==["华建","永固"]
    assert {r["party"] for r in shared["00001"]["receipts"]}=={"华建","永固"}
    assert all(c["basis"] for c in merged["collisions"])


def test_both_parties_contribute_quantity(merged):
    rows=merged["stages"][3]["rows"]
    by_party={}
    for row in rows: by_party.setdefault(row["party"],[]).append(row)
    assert set(by_party)=={"华建","永固"}
    assert sum(Decimal(r["increment_qty"]) for r in by_party["华建"])>0
    assert sum(Decimal(r["increment_qty"]) for r in by_party["永固"])>0


def test_increment_not_dropped_by_shared_item_period(merged):
    # 两家同清单同周期也不能去重掉一方
    assert merged["stages"][3]["metrics"]["parties"]==2
    assert not any(q["reason"]=="DUPLICATE_PERIOD" for q in merged["stages"][3]["quarantine"])


def test_valuation_totals_equal_party_sum(merged):
    m=merged["stages"][5]["metrics"]
    parts=m["parties"]
    assert set(parts)=={"华建","永固"}
    assert Decimal(m["expected_total"])==sum(Decimal(v["expected_total"]) for v in parts.values())
    assert Decimal(m["reported_total"])==sum(Decimal(v["reported_total"]) for v in parts.values())
    assert m["differences"]==sum(v["differences"] for v in parts.values())


def test_receipt_no_traceable_per_row(merged):
    for row in merged["stages"][6]["rows"]:
        assert row["receipt_no"]
    receipts=[r["receipt_no"] for r in merged["stages"][6]["rows"]]
    assert len(receipts)==len(set(receipts))


def test_generated_receipt_no_when_absent():
    from app.modules.m1_claims.rules import evaluate
    raw=("claim_id,item,period,cumulative_qty,previous_qty,change_id,reversal,reported,note\n"
         "00001,001,2026-11,125,100,C0,none,2000,x\n").encode()
    row=evaluate(raw)["rows"][0]
    assert row["receipt_no"] and row["party"]=="未标注"


def test_same_party_conflict_keeps_both_receipts(merged):
    adj=merged["adjudications"]
    assert len(adj)==1
    a=adj[0]
    assert a["party"]=="华建" and a["claim_id"]=="00003"
    assert a["kept"]["receipt_no"]=="HJ-003" and a["rejected"]["receipt_no"]=="HJ-003R"
    assert set(a["fields"])=={"cumulative_qty","reported","note"}
    assert a["basis"]


def test_conflict_row_quarantined_with_original(merged):
    q=[x for x in merged["stages"][6]["cumulative_quarantine"] if x["reason"]=="DUPLICATE_CONFLICT"]
    assert len(q)==1 and q[0]["receipt_no"]=="HJ-003R" and q[0]["_raw"]


def test_archive_has_receipt_and_basis_rows(client):
    saved=execute(load_sample("merged.csv"))
    resp=client.get("/api/runs/"+saved["run_id"]+"/archive")
    rows=list(csv.reader(io.StringIO(resp.data.decode("utf-8-sig"))))
    header,body=rows[0],rows[1:]
    assert "receipt_no" in header and "party" in header
    kinds={r[3] for r in body}
    assert {"accepted","quarantine","shared_number","conflict_basis"}<=kinds
    receipts={r[6] for r in body if r[3]=="accepted"}
    assert {"HJ-001","YG-001","HJ-003"}<=receipts


def test_legacy_sample_without_party_still_works():
    r=calculate(load_sample("legacy.csv"))
    assert r["stages"][5]["metrics"]["balanced"] is True
    assert r["stages"][6]["metrics"]["ready"] is True


def test_previous_revision_scoped_to_party():
    from app.modules.m4_increment.rules import evaluate
    rows=[{"claim_id":"00001","party":"华建","item":"001","period":"2026-11","cumulative_qty":"250","previous_qty":"225","unit_price":"120","reversal":"none"},
          {"claim_id":"00001","party":"永固","item":"001","period":"2026-11","cumulative_qty":"60","previous_qty":"40","unit_price":"100","reversal":"none"}]
    exact=evaluate(rows,{"parameters":{"previous_revisions":{"华建|00001":"230"}}})["rows"]
    assert {r["party"]:r["increment_qty"] for r in exact}=={"华建":"20","永固":"20"}
    # 裸编号在两方共号时不得套用到另一家
    bare=evaluate(rows,{"parameters":{"previous_revisions":{"00001":"230"}}})["rows"]
    assert {r["party"]:r["increment_qty"] for r in bare}=={"华建":"25","永固":"20"}


def test_previous_revision_bare_key_without_collision():
    from app.modules.m4_increment.rules import evaluate
    rows=[{"claim_id":"00009","party":"华建","item":"001","period":"2026-11","cumulative_qty":"250","previous_qty":"225","unit_price":"120","reversal":"none"}]
    r=evaluate(rows,{"parameters":{"previous_revisions":{"00009":"200"}}});assert r["rows"][0]["increment_qty"]=="50"


def test_duplicate_external_receipt_is_quarantined():
    from app.modules.m1_claims.rules import evaluate
    raw=("claim_id,party,item,period,cumulative_qty,previous_qty,change_id,reversal,reported,receipt_no,note\n"
         "00001,华建,001,2026-11,250,225,C1,none,2550,ABCD,x\n"
         "00002,永固,001,2026-11,120,100,C1,none,2040,ABCD,y\n").encode()
    r=evaluate(raw)
    assert r["metrics"]["accepted"]==1
    assert r["quarantine"][0]["receipt_no"]=="ABCD" and r["quarantine"][0]["claim_id"]=="00002"
    assert r["adjudications"][0]["scope"]=="回单号重复"


def test_certificate_totals_tie_to_deductions_and_valuation(merged):
    ded=merged["stages"][4]["metrics"];val=merged["stages"][5]["metrics"];cert=merged["stages"][6]["metrics"]
    assert Decimal(cert["expected_total"])==Decimal(ded["net_total"])==Decimal(val["expected_total"])
    assert set(cert["parties"])==set(val["parties"])==set(ded["parties"])=={"华建","永固"}
    for name in cert["parties"]:
        assert cert["parties"][name]["expected_total"]==ded["parties"][name]["net_total"]==val["parties"][name]["expected_total"]
    assert cert["party_count"]==2 and cert["shared_numbers"]==2


def test_merged_run_stable_and_idempotent(merged):
    a=execute(load_sample("merged.csv"));b=execute(load_sample("merged.csv"))
    assert a["run_id"]==b["run_id"] and len(store.history())==1
