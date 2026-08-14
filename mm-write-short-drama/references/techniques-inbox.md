# 对话与批量知识录入

## 对话粘贴

把用户原文完整传入，不先用改写文本替代原始资料：

```bash
python3 scripts/ingest_knowledge.py \
  --kb /path/to/knowledge-base \
  --text "用户粘贴的完整原文，包含规则、范围和说明" \
  --rule "从原文提炼的一条原子规则" \
  --source-name codex-conversation.md \
  --status draft
```

`--text` 保存证据，`--rule` 保证卡片正文只有一条原子规则。若原文本身就是单一规则，可省略 `--rule`。用户已明确确认且字段完整时可改为 `--status active`。生成后复核分类、适用范围、理由、例外和例子。

## 批量 Inbox

```bash
python3 scripts/ingest_knowledge.py \
  --kb /path/to/knowledge-base \
  --all-inbox
```

也可把多个文件或目录作为位置参数传入。只处理 Markdown/TXT；跳过 README 和隐藏文件。原文件留在 inbox，副本进入 `sources/`。

## 冲突裁决

```bash
python3 scripts/ingest_knowledge.py \
  --kb /path/to/knowledge-base \
  --resolve KBC-XXXXXXXXXXXX \
  --decision keep-existing
```

决策可为 `keep-existing`、`activate-new`、`keep-both`。两者并存必须用 `--note` 写清已经分离的适用范围。未裁决规则保持 `pending-conflict`，不得调用。
