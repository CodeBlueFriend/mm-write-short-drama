# Humanizer 短剧适配 v1.0.0

上游固定为 `blader/humanizer@9862685f575c65a8247f90369951df1b3416e3d6`（3.0.0，MIT）。本文件与上游规则分开维护。

## 随附规则与校验工具

以实际安装的技能目录为基准，读取 [固定版本的规则](vendor/humanizer.md)，使用同一技能目录下的 `scripts/humanizer_gate.py`。规则和校验器都随技能分发，校验器仅使用 Python 标准库。上游规则按 [MIT 许可](vendor/humanizer-LICENSE) 分发，版本以 [固定提交](https://github.com/blader/humanizer/tree/9862685f575c65a8247f90369951df1b3416e3d6) 为准。

逐集保存草稿，再由当前模型按下文实际编辑并复查。对每个最终 Markdown（含交付的前置正文）执行以下命令，路径按项目替换：

```bash
python3 "$SKILL_DIR/scripts/humanizer_gate.py" verify --draft "$DRAFT" --final "$FINAL"
python3 "$SKILL_DIR/scripts/humanizer_gate.py" record \
  --draft "$DRAFT" --final "$FINAL" --adapter short-drama \
  --attestation model-edit-complete --log "$PROJECT/.humanizer/runs.jsonl"
python3 "$SKILL_DIR/scripts/humanizer_gate.py" check \
  --final "$FINAL" --log "$PROJECT/.humanizer/runs.jsonl"
```

每次导出前先检查全部定稿的记录。已有记录可沿用原路径（旧版也可能以终稿所在目录下的 `.humanizer/runs.jsonl` 为默认位置），正文与记录匹配时无需重做。变动后重新编辑并验收。原稿快照和哈希记录留在项目内。纯版式模板预览按 Word 规则验收即可。

## 编辑约束

- 只编辑观众/演员/制片会读到的自然语言。集号、场号、时空、人物名、动作/表演提示格式、控制字段、ID、路径、模板变量、时间码和逐字引用不改。
- 保护人物关系、剧情信息、冲突、伏笔、道具、信息差与当场目的；不新增剧情事实。对白按角色身份、目的和声纹分别编辑，不能统一成同一种口吻。
- 必要重复、卡点和表演节奏可保留。无法安全修改的台词保留原句；Humanizer 检查不意味着必须改字。
- 长文本逐集/逐场处理，携带相关人物状态、前后场和连续性账本，处理后复查衔接。
- 不承诺通过 AI 检测；日志不记录全文。
