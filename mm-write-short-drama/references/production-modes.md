# 真人与 AI 制作适配

新项目按“AI或真人 → 创作来源 → 题材等需求 → 单集时长 → 期望集数”逐项取得用户选择；已明确的项直接记录；制作方式未选时先问AI或真人，选完立即问创作来源，不能先问来源或题材。题材等普通需求可先标待定。四项齐全后才构思故事底稿和大纲。`hybrid/unspecified` 保留旧项目与评估兼容，不代替新项目的真人/AI选择。

## 本次固定时长策略

以下是用户为本次程序指定的项目策略，不是新查到的平台规定，不为此上网核规范。

| 制作方式 | 供用户选择的单集时长 | 边界 |
|---|---|---|
| 真人 | 推荐90秒；常见60—180秒，爆款常规80—120秒 | 新项目硬上限180秒；旧有超过180秒的存量稿不作为新项目默认。 |
| AI | 主流50—60秒，90秒可选 | 超过120秒少见；用户明确自定义可保留，标为非常规，不改成绝对禁令。 |

时长可用具体秒数或范围；不把推荐值当成已选。期望集数可为 `60` 或 `40-60`，是故事开发的目标，允许合理浮动。实际规划总数与理由另存 `.drama/episode-plan.json`，`state.totalEpisodes` 镜像实际数；偏离具体数或超出范围时说明剧情理由，最终随大纲人工确认，不设固定浮动比例。

## 选择来源

来源有三种：自己编写（`original`）、已有素材改编（`adaptation`）、检索近期热门剧本后改编/再创作（`market_research`）。旧 `source_remix` 仅作兼容，不作为新项目第四个默认选项。只有简介或宣发时如实记录材料层级，不能冒称已读完整剧本；来源证据与改编取舍见 [source-intake.md](source-intake.md)。

## 记录选择

`set-specs` 的参数必须转录用户真实选择。以下引号内容只说明格式，必须换成真实原话与真实消息定位；不把示例当授权。

```bash
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" set-specs \
  --production-mode live_action --user-quote '用户选择真人的原话' --message-ref '真实消息定位'
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" set-specs \
  --source-mode original --user-quote '用户选择自己编写的原话' --message-ref '真实消息定位'
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" set-specs \
  --duration-seconds 90 \
  --user-quote '用户选择90秒的原话' --message-ref '真实消息定位'
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" set-specs \
  --episode-count '40-60' \
  --user-quote '用户期望40到60集的原话' --message-ref '真实消息定位'
```

来源后了解题材等普通需求，再记录时长与期望集数。`init --mode` 只决定骨架、不算来源选择；明确来源时程序补齐相应空骨架及索引依赖，不覆盖已有正文；切换来源的证据归档与重置见 [source-intake.md](source-intake.md)。范围时长用 `--duration-range 80-120` 替代 `--duration-seconds 90`。`.drama/production-specs.json` 保存期望与逐步选择依据；未齐保持 `awaiting_production_specs`，`status` 按 `productionMode → sourceMode → duration → episodeCount → episodePlan` 指明下一项。新增来源/时长/集数初始化参数无回执会被拒绝；旧制作方式/总数参数单独出现只作待核候选，旧字段或有值但缺回执的sourceMode不得猜成已选，须用真实原话补选。

故事与剧本主流程共用；制作方式也影响以下可行性审核。其他限制未提供时标记风险，不自行删改。

## 真人制作

检查演员数量与调度、场地与转场、日夜/天气、群演/儿童/动物/车辆、特技/打斗/危险动作、妆造连续性、拍摄周期和预算。同时检查演员是否有可表演行为，不把降本等同于两人站着解释剧情。

## AI 制作

检查多人同框稳定性、角色外观/服饰、无意义换景、复杂手部交互、多人打斗、镜面/文字屏幕、连续动作拆分、关键道具跨镜一致和生成失败对叙事的影响。

## 风险输出

| 位置 | 风险 | 严重度 | 叙事必要性 | 替代呈现 | 是否需批准 |
|---|---|---|---|---|---|

替代呈现优先保持剧情功能：拆动作、换视角、使用反应镜头/声音/结果镜头、减少无必要同框、固定造型锚点。删除大场面、改变角色数量、改结局或削弱核心冲突必须由用户批准。
