from flask import render_template
from app.config import MODULES,TITLE,SHORT
from app.pipeline import execute,load_sample
from app import store
def register_pages(app):
    def page(index):
        run=store.latest() or execute(load_sample("dirty.csv"))
        stage=run["stages"][index]
        rows=stage["rows"]
        columns=[['party', 'claim_id', 'item', 'period', 'cumulative_qty', 'previous_qty', 'change_id', 'reported', 'receipt_no'],
                 ['party', 'claim_id', 'item', 'unit', 'cumulative_qty', 'previous_qty', 'receipt_no'],
                 ['party', 'claim_id', 'period', 'approved_change', 'unit_price', 'receipt_no'],
                 ['party', 'claim_id', 'period', 'cumulative_qty', 'approved_previous', 'increment_qty', 'gross_amount', 'receipt_no'],
                 ['party', 'claim_id', 'item', 'gross_amount', 'retention', 'advance_recovery', 'expected', 'receipt_no'],
                 ['party', 'claim_id', 'item', 'expected', 'reported', 'difference', 'status', 'receipt_no'],
                 ['party', 'claim_id', 'period', 'expected', 'status', 'receipt_no']][index]
        labels={'party': '分包商', 'claim_id': '申报编号', 'item': '清单项', 'period': '申报周期', 'cumulative_qty': '本次累计量', 'previous_qty': '前审累计量', 'change_id': '变更单', 'reported': '申报净额', 'unit': '单位', 'approved_change': '已批变更', 'unit_price': '单价 / 元', 'approved_previous': '修订前审量', 'increment_qty': '本期工程量', 'gross_amount': '本期总额', 'retention': '质保金', 'advance_recovery': '预付款扣回', 'expected': '实算净额', 'difference': '净额差异', 'status': '结论', 'gross_total': '本期总额合计', 'net_total': '实算净额合计', 'receipt_no': '原始回单号', 'parties': '分包商数', 'same_number_collisions': '同号跨方', 'conflicts': '同方冲突', 'records': '记录数', 'shared_numbers': '共号编号', 'source_lines': '来源行数', 'ready': '可归档', 'sha256': '校验摘要', 'differences': '差异项', 'expected_total': '实算净额合计', 'reported_total': '申报净额合计'}
        for key,label in {'accepted_inputs': '采纳来源行', 'quarantine_inputs': '隔离来源行', 'output_records': '结果记录', 'input': '输入行', 'excluded': '排除行', 'balanced': '行数平衡', 'blank': '空行', 'repeated_headers': '分段表头', 'encoding': '编码', 'duplicate': '重复行', 'quarantine': '隔离行', 'accepted': '采纳行', 'negative_claims': '负进度行', 'items': '清单项数', 'versions': '变更版本', 'source_lines': '来源行数'}.items(): labels.setdefault(key,label)
        parties=run["stages"][5]["metrics"].get("parties",{}) if len(run["stages"])>5 else {}
        current=store.current_publication()
        published_line=("已发布 "+current["run_id"]+" V"+str(current["version"])) if current else "尚未发布"
        return render_template(f"m{index+1}.html",title=TITLE,short=SHORT,modules=MODULES,index=index,run=run,stage=stage,rows=rows,columns=columns[:12],history=store.history(),labels=labels,parties=parties,collisions=run.get("collisions",[]),adjudications=run.get("adjudications",[]),published_line=published_line)
    app.add_url_rule("/",view_func=lambda:page(4))
    for index,(slug,name) in enumerate(MODULES):
        app.add_url_rule("/"+slug,endpoint="page_"+slug,view_func=lambda index=index:page(index))
