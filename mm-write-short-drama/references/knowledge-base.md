# 个人编剧知识库工作流

## 分离原则

把 `SKILL.md` 和 `references/` 视为稳定流程，把仓库根目录 `knowledge-base/` 视为个人长期知识。升级 Skill 时保留知识库。随技能发布的只读内置卡位于 `assets/builtin-knowledge/cards/`，在个人库录入或重建索引时保留两处存储的独立性。

## 录入

用户在对话中粘贴技巧时，先把原文原样传给 `ingest_knowledge.py --text`。用户提供文件时读取 `knowledge-base/inbox/`；脚本会复制到不可变 `sources/`，但不移动或删除 inbox 文件。

脚本把半结构化块、项目符号或普通文字提炼为候选原子规则，并做启发式分类。完成后必须复核每张新卡：一张卡是否只有一个可执行规则；分类和阶段是否准确；题材/制作范围是否过宽；理由、例外和正反例是否充分。自动分类是初稿，不是事实。

默认使用 `draft`。若用户这次明确要求“加入知识库”且卡片字段完整，可用 `--status active`；但任何疑似冲突都会被脚本强制改为 `pending-conflict`。

## 重复和冲突

- 完全相同或高度相似规则不创建新卡、不覆盖旧卡，在 `conflicts/duplicates.jsonl` 追加记录；原始资料仍保存在 `sources/`。
- 范围重叠且措辞方向相反的规则创建为 `pending-conflict`，在 `conflicts/open.jsonl` 记录证据。
- 未确认冲突不得检索或应用。向用户展示双方规则 ID、适用范围、冲突点和三种选择：保留旧规则、启用新规则并停用旧规则、明确区分范围后两者并存。
- 用 `ingest_knowledge.py --resolve ...` 记录用户裁决。状态变化前自动把旧卡快照保存到 `archive/`；任何历史和原始来源都不删除。

## 检索与调用

在策划、结构、分集、场景、对白、改编和审核各阶段分别查询，不一次加载全库。命令模板：

```bash
python3 scripts/search_knowledge.py "当前任务摘要" \
  --stage episode \
  --genre 女频复仇 \
  --production-mode live-action \
  --limit 8 \
  --format context
```

默认只返回 `active`。无个人库时直接查询内置卡。命令会自动查找工作区附近的个人库，也可用 `--kb /path/to/knowledge-base` 指定。查询范围和任务都匹配时，同一能力的个人卡优先于内置卡。结果会标出内置或个人来源。按以下顺序裁决：当前项目明确要求 → 项目锁定事实 → 安全/版权硬约束 → active hard → 题材/制作范围匹配的 preferred → optional → experimental。知识卡与前三项冲突时，不改项目；记录该卡被覆盖及原因。

应用前检查 `exceptions`。只有规则实际改变了方案、文字或审核结论，才把 ID 记为“实际使用”；只看过但未使用的规则可记为“检索但未使用”。

## 审核记录

在审核报告增加：

```markdown
## 个人知识调用
- 实际使用的知识规则 ID：EPISODE-XXXX、DIALOGUE-YYYY
- 检索但未使用：HOOK-ZZZZ（原因：本场不满足适用范围）
- 被项目要求覆盖：OPENING-AAAA（原因：项目锁定为慢热冷开场）
- 未解决冲突：无
```

交付前运行 `validate_knowledge.py`。源文件哈希变化、卡片字段缺失、重复规则、未解决冲突状态错误均视为校验失败。
