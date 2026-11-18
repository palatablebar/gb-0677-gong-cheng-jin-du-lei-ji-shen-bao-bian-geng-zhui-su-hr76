from pathlib import Path
import os
ROOT=Path(__file__).resolve().parent.parent
DATA_DIR=Path(os.environ.get("DATA_DIR", "/tmp/progressclaim"))
TITLE='工程进度累计申报与变更追溯'
SHORT='progressclaim'
COLUMNS=['claim_id', 'item', 'period', 'cumulative_qty', 'previous_qty', 'change_id', 'reversal', 'reported', 'note']
MODULES=[('claims', '申报采信'), ('billitems', '清单映射'), ('changes', '变更定版'), ('increment', '累计还原'), ('deductions', '扣回核算'), ('valuation', '进度对账'), ('certificates', '签证归档')]
# 分包商/申报单位：编号由各分包商独立起编，必须与申报编号联合识别。
PARTY='party'
PARTY_ALIASES=('party','分包商','申报单位')
UNSPECIFIED_PARTY='未标注'
# 原始回单号：外部凭据，缺失时按 分包商/编号/源行 生成可回查的稳定编号。
RECEIPT='receipt_no'
RECEIPT_ALIASES=('receipt_no','回单号','原始回单号')
RULE_VERSION="2026.11.18-r2"
