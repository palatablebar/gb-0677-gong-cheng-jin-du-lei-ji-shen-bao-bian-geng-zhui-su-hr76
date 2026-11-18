import sqlite3,json
from datetime import datetime,timezone
from app.config import DATA_DIR
from app.errors import DomainError
def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA_DIR/"records.db",timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,decision TEXT NOT NULL DEFAULT '待复核')")
    db.execute("CREATE TABLE IF NOT EXISTS published (slot INTEGER PRIMARY KEY CHECK (slot=1),run_id TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,published_at TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS published_log (seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL,version INTEGER NOT NULL,published_at TEXT NOT NULL)")
    return db
def save(run_id,payload):
    """同源重跑落同一 run_id：已存在则原样返回，不新增批次。"""
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES (?,?)",(run_id,json.dumps(payload,ensure_ascii=False)))
    return get(run_id)
def get(run_id):
    with connect() as db: row=db.execute("SELECT payload,version,decision FROM runs WHERE id=?",(run_id,)).fetchone()
    if not row: raise DomainError("NOT_FOUND","批次不存在",404)
    return {**json.loads(row[0]),"version":row[1],"decision":row[2]}
def latest():
    with connect() as db: row=db.execute("SELECT id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
    return get(row[0]) if row else None
def history():
    with connect() as db: return [{"run_id":i,"version":v,"decision":d} for i,v,d in db.execute("SELECT id,version,decision FROM runs ORDER BY rowid DESC")]
def review(run_id,version,decision):
    if decision not in {"已复核","退回复核"}: raise DomainError("BAD_DECISION","复核状态无效")
    with connect() as db:
        cursor=db.execute("UPDATE runs SET version=version+1,decision=? WHERE id=? AND version=?",(decision,run_id,version))
        if cursor.rowcount!=1:
            if not db.execute("SELECT 1 FROM runs WHERE id=?",(run_id,)).fetchone(): raise DomainError("NOT_FOUND","批次不存在",404)
            raise DomainError("STALE_VERSION","版本已更新，请刷新",409)
    return get(run_id)
def current_publication():
    """当前对外生效的版本。发布失败时保持上一版指针不动。"""
    with connect() as db: row=db.execute("SELECT run_id,version,payload,published_at FROM published WHERE slot=1").fetchone()
    if not row: return None
    return {"run_id":row[0],"version":row[1],"payload":json.loads(row[2]),"published_at":row[3]}
def _verify(run):
    stages=run.get("stages") or []
    if not stages or not stages[-1].get("metrics",{}).get("ready"): raise DomainError("NOT_READY","批次未通过归档校验，不能发布")
    reconcile=next((s["metrics"] for s in stages if "balanced" in s.get("metrics",{})),None)
    archive=stages[-1]["metrics"]
    if not reconcile or reconcile.get("balanced") is not True: raise DomainError("UNBALANCED","来源行未对平，不能发布")
    if archive.get("source_lines")!=reconcile.get("accepted_inputs"): raise DomainError("UNBALANCED","来源行与对账不一致，不能发布")
    return archive
def publish(run_id,expected_version=None):
    """原子发布：先校验再在同一事务内切换指针。任何失败都不改动当前生效版本。"""
    run=get(run_id);_verify(run)
    if expected_version is not None and expected_version!=run["version"]: raise DomainError("STALE_VERSION","版本已更新，请刷新",409)
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT run_id,version FROM published WHERE slot=1").fetchone()
        if row and row[0]==run_id and row[1]==run["version"]:
            return {**current_publication(),"reused":True}
        db.execute("INSERT INTO published(slot,run_id,version,payload,published_at) VALUES (1,?,?,?,?) "
                   "ON CONFLICT(slot) DO UPDATE SET run_id=excluded.run_id,version=excluded.version,payload=excluded.payload,published_at=excluded.published_at",
                   (run_id,run["version"],json.dumps(run,ensure_ascii=False),datetime.now(timezone.utc).isoformat()))
        db.execute("INSERT INTO published_log(run_id,version,published_at) VALUES (?,?,datetime('now'))",(run_id,run["version"]))
    return {**current_publication(),"reused":False}
def published_history():
    with connect() as db: return [{"run_id":r,"version":v,"published_at":t} for r,v,t in db.execute("SELECT run_id,version,published_at FROM published_log ORDER BY seq DESC")]
