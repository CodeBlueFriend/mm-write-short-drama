# 个人编剧知识库

这里保存持续增长的个人编剧知识；`mm-write-short-drama/` 保存稳定工作流。升级 Skill 时不要覆盖本目录。

## 目录

- `inbox/`：待处理 Markdown/TXT，批量录入后仍原地保留。
- `sources/`：脚本保存的不可变原始资料副本；不得删除或原地修改。
- `cards/`：一条原子规则一张 Markdown 知识卡。
- `index/`：可重建的 JSONL 检索索引和录入日志。
- `conflicts/`：重复项、待裁决冲突和裁决记录，均为追加式日志。
- `archive/`：规则状态或版本变化前的快照，不作为默认检索结果。

知识库只使用 Markdown 与 JSONL，不依赖向量数据库。默认检索只返回 `active` 卡片；`draft`、`pending-conflict`、`duplicate`、`rejected`、`deprecated`、`archived` 不会自动应用。
