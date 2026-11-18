import pytest
from app.pipeline import calculate,execute,load_sample
from app import store
from app.errors import DomainError


@pytest.fixture
def merged_run(): return execute(load_sample("merged.csv"))


def test_publish_twice_is_idempotent(merged_run):
    first=store.publish(merged_run["run_id"])
    second=store.publish(merged_run["run_id"])
    assert first["run_id"]==second["run_id"] and first["version"]==second["version"]
    assert second["reused"] is True
    assert len(store.published_history())==1


def test_failed_publish_keeps_previous(monkeypatch):
    good=execute(load_sample("merged.csv"))
    published=store.publish(good["run_id"])
    # 构造一个校验失败的批次：归档行数与对账不一致
    bad=calculate(load_sample("merged.csv"))
    bad["run_id"]="broken-run"
    bad["stages"][-1]["metrics"]["source_lines"]=0
    store.save("broken-run",bad)
    with pytest.raises(DomainError) as e: store.publish("broken-run")
    assert e.value.code=="UNBALANCED"
    current=store.current_publication()
    assert current["run_id"]==published["run_id"] and current["version"]==published["version"]


def test_unready_batch_not_published():
    good=execute(load_sample("merged.csv"))
    store.publish(good["run_id"])
    bad=calculate(load_sample("merged.csv"));bad["run_id"]="not-ready";bad["stages"][-1]["metrics"]["ready"]=False
    store.save("not-ready",bad)
    with pytest.raises(DomainError) as e: store.publish("not-ready")
    assert e.value.code=="NOT_READY"
    assert store.current_publication()["run_id"]==good["run_id"]


def test_rerun_same_batch_adds_nothing(merged_run):
    before=len(store.history())
    again=execute(load_sample("merged.csv"))
    assert again["run_id"]==merged_run["run_id"]
    assert len(store.history())==before


def test_rerun_different_content_new_batch(merged_run):
    before=len(store.history())
    from app.pipeline import load_sample as load
    other=execute(load("dirty.csv"))
    assert other["run_id"]!=merged_run["run_id"]
    assert len(store.history())==before+1


def test_publish_endpoint_idempotent_and_guarded(client):
    run=client.post("/api/runs",json={"sample":"merged.csv"}).get_json()
    url="/api/runs/"+run["run_id"]+"/publish"
    assert client.post(url).status_code==200
    assert client.post(url).status_code==200
    assert len(client.get("/api/publication").get_json()["history"])==1
    assert client.post(url,json={"version":99}).status_code==409


def test_published_payload_is_frozen_copy(merged_run):
    published=store.publish(merged_run["run_id"])
    store.review(merged_run["run_id"],1,"已复核")
    after=store.current_publication()
    assert after["payload"]["stages"]==published["payload"]["stages"]
