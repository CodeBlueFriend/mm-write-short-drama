# Humanizer 短剧适配 v2

此流程用于正式稿；独立试戏和局改按 [主入口](../SKILL.md) 返回候选稿，不要求先登记正式交付记录。润色默认 `local`：先定位需要改的台词或动作，说明问题，再逐处编辑。允许 `off` 保留已清楚准确的原句；`full` 仅在项目明确选择后使用。三种设置均须完成最终事实、声纹与承接复核。结构或动机缺口回到大纲、分集或场次，不由润色补剧情。

定位问题前仍须通读整场和相关上下文，检查专业词是否有歧义、复合动作是否需要分拍，以及这些变化是否真能帮助表演。局部编辑不等于只扫单句语法。完整通读后可以只改几处，也可以原样通过；以具体改善及事实保持为依据，不把改字数量当成绩。独立主笔稿按 [主笔写戏](lead-writer.md) 把原句、具体问题与不可变事实送回同一主笔，由主会话对读修订前后稿，不额外合写。

## 执行位置与版本

如启用 Humanizer，查找实际安装位置和固定版本。上游规则为 `blader/humanizer@9862685f575c65a8247f90369951df1b3416e3d6`。同级 `humanizer/SKILL.md`、`mm-humanizer-gate/scripts/humanizer_gate.py` 是可选外部适配器；仓库自带 `scripts/polish_guard.py` 留存本地差异和最终语义复核，无外部依赖也可使用 `off`。不要把缺少改写器当成必须强制改字的理由。

同一项目由一个位置负责改写，记录规则路径、规则摘要、编辑者和实际调用链。旧包装、内置流程、独立技能不得对同一稿重复全量润色。已通过且哈希一致的最终复核可复用；正文修改后失效。程序不能证明自然语言语义相同，复核人必须读实际前后文。日志只放必要原场差异，私人项目不进入公开源码。

## 差异与语义门

保留已通过结构审查的底稿。集数、场次、人物、ID、项目字段、来源、锁定事实、道具归属、伏笔、否定、条件、金额、日期和许诺均受保护；不把含蓄变成明说，不删有作用的重复或承诺中的限定词。

```bash
python3 "$SKILL_DIR/scripts/polish_guard.py" inspect \
  --before project/work/EP001-reviewed.md --after project/episodes/EP001.md \
  --output project/work/EP001-diff.json
```

`inspect` 给出稳定改动 ID、前后行号和保守风险标记。它能检测所覆盖的数字、人称、否定、条件等变化，不能自动判断事实、责任归属或潜台词。未标记的改动同样须逐处读。复核 JSON 填写本次 `beforeHash`、`afterHash`、`reviewer`、`evidence`、`semanticVerified: true`、`mode`、实际 `callChain`，以及 `checked` 中的 `characters / subject_object / negation / conditions / time / amounts / promises / voice / continuity`。`changes` 每条给 `id / meaningPreserved / reason`；保护词差异另列有具体依据的 `editorApproval`。语义未经批准改变时恢复原句或退编剧修订，不能勾选通过。

```bash
python3 "$SKILL_DIR/scripts/polish_guard.py" record \
  --before project/work/EP001-reviewed.md --after project/episodes/EP001.md \
  --review project/work/EP001-semantic-review.json \
  --output project/.drama/polish/EP001.json
python3 "$SKILL_DIR/scripts/polish_guard.py" check \
  --after project/episodes/EP001.md --review project/.drama/polish/EP001.json
```

`off` 使用完全相同的前后稿，仍记录真实复核及九项检查；无需虚构编辑调用。已使用外部门时把它的真实路径和记录列进调用链；外部 `verify` 成功不能替代这里的逐差异语义复核。

## 选择默认设置的证据

相同已审底稿保留未润色、当前默认和局部润色三版，固定模型和上游条件；在独立上下文隐藏标签并打乱顺序阅读，记录收益、损失与无法判断。技术门是否发现编辑伤害与编辑本身是否改善阅读分开报告。未实际运行的版本不写成已盲评。优质原文可原样通过。
