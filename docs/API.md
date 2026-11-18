# 接口

模块GET使用仓内样例，模块POST可传csv或rows与context，直接计算当前规则。/api/runs使用完整流水线并原子保存。每个阶段返回rows、quarantine、metrics；后续阶段还返回累计隔离。/api/upload接收multipart文件file。/api/runs/<id>/archive只导出一份带清单与证据的CSV。

`/api/claims` 额外返回 `collisions`（跨分包商同号编号、各方原始回单与源行、裁决依据）与 `adjudications`（同方同编号冲突的保留/隔离回单及裁决依据）。批次顶层同样带这两类证据，供导出与复核。

`POST /api/runs/<id>/publish` 发布当前批次，可带 `version` 做乐观锁，返回 `run_id`、`version`、`published_at`、`reused`。归档未就绪或来源行未对平返回 422（`NOT_READY`/`UNBALANCED`），版本失效返回 409；失败时当前生效版本保持不变。同批同版重复发布返回 `reused=true`，不新增版本。`GET /api/publication` 返回当前生效版本与发布历史。

样例可选 `dirty.csv`、`clean.csv`、`legacy.csv`、`merged.csv`（两家分包商同号合并批）。
