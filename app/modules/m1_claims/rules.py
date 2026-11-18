import csv,io
from app.config import COLUMNS,PARTY,PARTY_ALIASES,RECEIPT,RECEIPT_ALIASES,UNSPECIFIED_PARTY
from app.errors import DomainError
from app.reasons import reject,claim_key
def decode(raw):
    for encoding in ("utf-8-sig","gb18030"):
        try: return raw.decode(encoding),encoding
        except UnicodeDecodeError: continue
    raise DomainError("ENCODING","无法识别文件编码")
OPTIONAL=set(PARTY_ALIASES)|set(RECEIPT_ALIASES)
def split_header(header):
    """基础列必须齐全且保持相对顺序；party/receipt_no 为可选列，位置不限。"""
    if not header: return None,None,None
    required=[name for name in header if name not in OPTIONAL]
    if required!=COLUMNS: return None,None,None
    if any(name not in COLUMNS and name not in OPTIONAL for name in header): return None,None,None
    party_column=next((name for name in header if name in PARTY_ALIASES),None)
    receipt_column=next((name for name in header if name in RECEIPT_ALIASES),None)
    return header,party_column,receipt_column
def receipt_no(party,claim_id,line):
    return f"{party}/{claim_id}/L{line}"
def evaluate(raw,context=None):
    text,encoding=decode(raw)
    if not text: raise DomainError("EMPTY_FILE","文件为空")
    if not text.strip(): raise DomainError("BLANK_ONLY","全部为空行")
    stream=csv.reader(io.StringIO(text,newline=""));raw_header=next(stream,None)
    header,party_column,receipt_column=split_header(raw_header)
    if header is None: raise DomainError("BAD_HEADER","表头不匹配")
    rows=[];bad=[];seen={};generated=set();duplicate=blank=repeated=count=0
    collisions=[];adjudications=[]
    try:
        for cells in stream:
            count+=1;line=stream.line_num
            if not cells or not any(c.strip() for c in cells): blank+=1;continue
            if cells==header: repeated+=1;continue
            row={"_line":line,"_sources":[line],"_raw":cells}
            if len(cells)!=len(header): bad.append(reject(row,"BAD_COLUMNS","列数不匹配"));continue
            row.update(dict(zip(header,[x.strip() for x in cells])))
            party=(row.get(party_column,"") or "").strip() if party_column else ""
            row[PARTY]=party or UNSPECIFIED_PARTY
            if not row[COLUMNS[0]]: bad.append(reject(row,"EMPTY_VALUE","业务键为空"));continue
            supplied=(row.get(receipt_column,"") or "").strip() if receipt_column else ""
            row[RECEIPT]=supplied or receipt_no(row[PARTY],row[COLUMNS[0]],line)
            if not supplied: generated.add(line)
            key=claim_key(row)
            if key in seen:
                kept=seen[key]
                if cells==kept["_raw"]: duplicate+=1
                else:
                    bad.append(reject(row,"DUPLICATE_CONFLICT","同方同编号不同取值"))
                    adjudications.append({
                        "conflict_id":f"CF-{len(adjudications)+1:03d}","scope":"同方同编号","key":key,
                        "party":row[PARTY],"claim_id":row[COLUMNS[0]],
                        "basis":"同方同编号取值冲突：保留首到行，后到行隔离；两条原始回单均留存，待人工裁决",
                        "fields":sorted(f for f in COLUMNS if row.get(f)!=kept.get(f)),
                        "kept":{"line":kept["_line"],"receipt_no":kept[RECEIPT],"raw":kept["_raw"]},
                        "rejected":{"line":line,"receipt_no":row[RECEIPT],"raw":cells}})
                continue
            seen[key]=row;rows.append(row)
    except csv.Error: raise DomainError("BAD_CSV","引号未闭合或文件损坏")
    if count==0: raise DomainError("HEADER_ONLY","仅有表头")
    if not rows and not bad: raise DomainError("BLANK_ONLY","全部为空行")
    # 回单号必须可唯一定位；外部提供的回单号重复则无法逐条回查，隔离后到行。
    by_receipt={}
    for row in [r for r in rows if r["_line"] not in generated]:
        prior=by_receipt.get(row[RECEIPT])
        if prior is not None:
            bad.append(reject(row,"DUPLICATE_CONFLICT","原始回单号已被前面的行占用，无法逐条回查"))
            adjudications.append({
                "conflict_id":f"CF-{len(adjudications)+1:03d}","scope":"回单号重复","key":row[RECEIPT],
                "party":row[PARTY],"claim_id":row[COLUMNS[0]],
                "basis":"同一原始回单号只能对应一条申报；保留首到行，后到行隔离待人工核对回单",
                "fields":["receipt_no"],
                "kept":{"line":prior["_line"],"receipt_no":prior[RECEIPT],"raw":prior["_raw"]},
                "rejected":{"line":row["_line"],"receipt_no":row[RECEIPT],"raw":row["_raw"]}})
            rows.remove(row)
            continue
        by_receipt[row[RECEIPT]]=row
    # 同号跨方：各分包商独立起编，同号不等于重复，两方全部保留并逐条留痕。
    by_number={}
    for row in rows: by_number.setdefault(row[COLUMNS[0]],[]).append(row)
    for number,group in by_number.items():
        parties=sorted({r[PARTY] for r in group})
        if len(parties)>1:
            collisions.append({
                "claim_id":number,"parties":parties,
                "receipts":[{"party":r[PARTY],"line":r["_line"],"receipt_no":r[RECEIPT],"raw":r["_raw"]} for r in group],
                "basis":"申报编号由各分包商独立编制，不具全局唯一性；按分包商+编号联合识别，全部保留，不做覆盖或丢弃"})
    metrics={"input":count,"accepted":len(rows),"quarantine":len(bad),"duplicate":duplicate,"blank":blank,
             "repeated_headers":repeated,"encoding":encoding,"parties":sorted({r[PARTY] for r in rows}),
             "same_number_collisions":len(collisions),"conflicts":len(adjudications)}
    return {"rows":rows,"quarantine":bad,"metrics":metrics,"collisions":collisions,"adjudications":adjudications}
