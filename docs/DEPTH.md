# 深度登记 工程进度累计申报与变更追溯

规模：中型。使用者：总包项目计量审核员。核心规则：累计申报必须减前期已审金额，变更按审批生效版本覆盖；负进度需关联冲回证据。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 申报采信 | 查看并运行申报采信 | `/api/claims` | `app/modules/m1_claims/rules.py` | `tests/test_m1.py` |
| M2 清单映射 | 查看并运行清单映射 | `/api/billitems` | `app/modules/m2_billitems/rules.py` | `tests/test_m2.py` |
| M3 变更定版 | 查看并运行变更定版 | `/api/changes` | `app/modules/m3_changes/rules.py` | `tests/test_m3.py` |
| M4 累计还原 | 查看并运行累计还原 | `/api/increment` | `app/modules/m4_increment/rules.py` | `tests/test_m4.py` |
| M5 扣回核算 | 查看并运行扣回核算 | `/api/deductions` | `app/modules/m5_deductions/rules.py` | `tests/test_m5.py` |
| M6 进度对账 | 查看并运行进度对账 | `/api/valuation` | `app/modules/m6_valuation/rules.py` | `tests/test_m6.py` |
| M7 签证归档 | 查看并运行签证归档 | `/api/certificates` | `app/modules/m7_certificates/rules.py` | `tests/test_m7.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧编码 | 默认解码失败 | 回退GB18030 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_legacy_encoding_real_sample` |
| TRAP-02 | BOM | 首列名多字符 | utf-8-sig | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_bom_real_sample` |
| TRAP-03 | 带引号换行 | 拆成两条 | csv逻辑行 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_quoted_newline_is_one_record` |
| TRAP-05 | 列数不匹配 | 静默错列 | 隔离原行 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_bad_columns_real_sample` |
| TRAP-08 | 前导零ID | 编码变形 | 全程字符串 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_identifier_preserved_real_sample` |
| TRAP-14 | 重复键冲突 | 后写覆盖 | 保留首条并隔离冲突行 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_duplicate_conflict_real_sample` |
| TRAP-18 | 空态三态 | 一律成功 | 分别错误码 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_three_empty_states` |
| TRAP-26 | 旧版本提交 | 覆盖新结果 | 版本条件更新 | `app/store.py` | `tests/test_e2e.py::test_stale_review_409` |
| TRAP-06 | 全角累计量 | 转换失败 | Decimal归一 | `app/values.py` | `tests/test_m2.py::test_fullwidth_quantity` |
| TRAP-07 | 累计量空值 | 按零冲回 | 隔离缺失 | `app/values.py` | `tests/test_m2.py::test_real_null_not_zero` |
| TRAP-10 | 分币舍入 | 浮点误差 | 分项量化后净额守恒 | `app/modules/m5_deductions/rules.py` | `tests/test_m5.py::test_fraction_rounds_to_cent` |
| TRAP-23 | 变更生效边界 | 旧价覆盖 | 按周期选择已批版本 | `app/modules/m3_changes/rules.py` | `tests/test_m3.py::test_effective_boundary` |
| TRAP-27 | 跨分包商同号 | 按编号全局去重，后到覆盖先到，另一家工程量丢失 | 业务键改为 分包商+编号，同号两方全保留，登记共号证据 | `app/modules/m1_claims/rules.py`、`app/reasons.py` | `tests/test_merged_parties.py` |
| TRAP-28 | 同号被当作重复导致漏量 | 只按清单+周期去重，另一家被隔离 | 去重键加入分包商 | `app/modules/m4_increment/rules.py` | `tests/test_merged_parties.py::test_increment_not_dropped_by_shared_item_period` |
| TRAP-29 | 原回单一覆盖即不可回查 | 只保留后到行，原始回单丢失 | 每行保留原始回单号与原始行，冲突双方回单都入裁决记录 | `app/archive.py`、`app/modules/m1_claims/rules.py` | `tests/test_merged_parties.py::test_same_party_conflict_keeps_both_receipts` |
| TRAP-30 | 发布失败破坏上一版 | 先删后写，失败后无版本 | 校验后单事务切换指针，失败不动当前版本 | `app/store.py` | `tests/test_publish.py::test_failed_publish_keeps_previous` |
| TRAP-31 | 同批重跑新增版本 | 每次发布都插入新版本 | 同批同版复用，重跑同源只复用批次 | `app/store.py`、`app/pipeline.py` | `tests/test_publish.py::test_publish_twice_is_idempotent` |

## 分包商同号规则

申报编号由各分包商独立起编，仅在分包商内唯一，因此业务键为「分包商+申报编号」。同一编号出现在两个分包商下时：两行都进入计算，不做覆盖或丢弃；M1 汇总 `collisions`（共号编号、双方原始回单号、源行），M6/M7 输出逐方合计与 `shared_numbers`，证据 CSV 以 `shared_number` 行固化依据。同方同编号取值冲突仍保留首条、隔离后到行，并生成 `CF-xxx` 裁决记录，含保留行与隔离行的回单号、原始内容、冲突字段与裁决依据，导出为 `conflict_basis` 行。缺失回单号时按 `分包商/编号/源行` 生成稳定可回查编号。

## 发布语义

`POST /api/runs/<id>/publish` 先做归档就绪与来源行对平校验，再在单事务内切换当前发布指针；校验或事务失败都不改动上一版。同批同版本重复发布返回 `reused`，不产生新版本；携带过期 version 返回 409。`published` 表保存发布时的完整冻结副本，复核状态变化不影响已发布内容；`published_log` 记录发布历史。

## 对账规则

输入原始逻辑行=最终采纳来源行+隔离来源行+重复行+空白行+分段表头。派生记录用_sources保存完整来源，因此分组不丢行。业务预期合计与上游申报合计之差等于逐行差异之和。结果按输入摘要、规则版本及参数产生唯一批次，事务写入；同源重跑只复用已有批次。

## 已知不覆盖

4MB以上文件需预先按业务键分批；不模拟生产支付与外部回调。人工复核只变更批次状态，不改写原始记录。
