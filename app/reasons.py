from app.config import PARTY,RECEIPT
REASONS={"BAD_COLUMNS":"列数不匹配","EMPTY_VALUE":"必填值为空","INVALID_NUMBER":"数字格式错误","INVALID_TIME":"时间缺少偏移或格式错误","DUPLICATE_CONFLICT":"同键取值冲突","UNKNOWN_REFERENCE":"引用不存在","STALE_VERSION":"版本已更新","EMPTY_FILE":"文件为空","HEADER_ONLY":"仅有表头","BLANK_ONLY":"全部为空行"}
def reject(row, code, detail):
    return {**row,"reason":code,"detail":detail}
def sources(row):
    return row.get("_sources", [row.get("_line",0)])
def party_of(row):
    return str(row.get(PARTY,"") or "")
def claim_key(row):
    """业务键：分包商 + 申报编号。编号仅在分包商内唯一。"""
    return f"{party_of(row)}|{row.get('claim_id','')}"
def receipt_of(row):
    return str(row.get(RECEIPT,"") or "")
