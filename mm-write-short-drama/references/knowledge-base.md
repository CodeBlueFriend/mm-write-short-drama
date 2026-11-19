# 个人编剧知识库工作流

## 分离原则

把 `SKILL.md` 和 `references/` 视为稳定流程，把工作区根目录 `knowledge-base/` 视为个人长期知识。Skill 内的 `knowledge-base/` 是随包提供的24张五书方法摘要，不含原书全文；旧版 `assets/builtin-knowledge/cards/` 的三张公开卡保留为兼容兜底。升级只替换随包库，不覆盖工作区个人卡，也不把随包卡写入个人索引。

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
  --kb /path/to/knowledge-base \
  --stage episode \
  --genre 女频复仇 \
  --production-mode live-action \
  --limit 8 \
  --format context
```

默认只返回 `active`。按以下顺序裁决：当前项目明确要求 → 项目锁定事实 → 安全/版权硬约束 → active hard → 题材/制作范围匹配的 preferred → optional → experimental。知识卡与前三项冲突时，不改项目；记录该卡被覆盖及原因。

未传 `--kb` 时先找当前目录及父目录的个人库，再合并随包库；即使没有个人库也能使用已审核的24张摘要卡。同一能力在当前任务、阶段、题材与制作范围内优先个人 active 卡，其次24张当前摘要，最后才是旧三张公开卡；不同范围的个人卡不覆盖其他题材，draft不抢占已启用卡。`--no-builtin` 可显式只查个人库。检索默认输出 `context`，包含完整动作、例外、自检和来源，`table` 仅供盘点。一次任务通常选《故事》1张，涉及两类问题最多2张；脚本默认限制2张，盘点才使用 `--story-limit 19 --limit 30`。查询读取当前卡片，避免旧索引造成卡片状态失真，默认不改写个人库。

## 固定五书导入与升级

随包输入位于 `assets/book-capability-inputs/`，固定到 `CodeBlueFriend/short-drama-book-skills@6e99009572a64f99d60134405fbf1cf200b0dfe4`。只使用仓库根目录 `knowledge-inbox` 的5份前四书材料和19份《故事》材料。输入清单包含各稿SHA-256及《故事》来源版本清单；脚本先校验全部输入，再修改目标库。

```bash
python3 scripts/import_book_capabilities.py --kb /tmp/five-books-draft --report /tmp/import-draft.json
python3 scripts/validate_knowledge.py --kb /tmp/five-books-draft --json
# 逐卡核对来源范围、例外和执行字段后，显式记录复核理由：
python3 scripts/import_book_capabilities.py --kb /tmp/five-books-draft \
  --activate-reviewed --review-note "填写本次实际完成的核验范围"
# 旧六卡升级需显式选择；仍保留同一卡ID、旧稿和上游版本信息：
python3 scripts/import_book_capabilities.py --kb /path/to/personal-knowledge-base \
  --upgrade-legacy-six --activate-reviewed --review-note "填写旧卡对读结果"
```

`capability_revision` 表示上游修订，与库内 `version` 分开。《故事》01—06为上游修订2，07—19为修订1。相同能力即使规则未改，也核对来源定位。已识别的旧六卡归档后更新；同修订的规则差异、多个当前版本和未决冲突均保留旧卡并报告，不静默覆盖。相同输入重跑不新增、不改写原卡或日志。通用 `ingest_knowledge.py` 仍负责普通技巧录入；不得用它的相似度查重替代能力版本迁移。

卡片中“原书已核”的文字是上游交接方的记录；本次只对固定导入稿及其清单完成核对，未重新逐字核验原书。保留纸本页码、第三方文件质量等缺口。核验范围见各卡 `source_verification` 与 `activation_review`。

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
