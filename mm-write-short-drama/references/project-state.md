# 项目状态、依赖与失效传播

## 机器状态文件

- `.drama/project-state.json`：项目修订、路由、当前阶段、单集状态和关键上游版本；`state.totalEpisodes` 镜像实际规划总数。
- `.drama/production-specs.json`：用户选择的制作方式、单集时长、期望集数（具体数/范围）及真实原话、消息定位；与实际规划总数分开。
- `.drama/episode-plan.json`：`plannedTotalEpisodes/planReason` 保存大纲实际总数与规划理由，不混入用户规格文件。
- `.drama/artifact-index.json`：产物路径、revision、审核状态和 `dependsOn` 依赖图。
- `.drama/invalidation-log.jsonl`：每次失效传播的追加日志；不得回写或删除旧事件。

它们是项目文件事实源的一部分，但不取代剧本文本和连续性账本。所有 JSON 都必须有 `schemaVersion`；对应结构见 `schemas/`。

## 恢复与提交

开始工作先运行 `scripts/workflow.py <project> status` 检测内容变动、持久化失效并恢复等待点，再运行 `scripts/validate_state.py <project>`。新项目缺制作方式、时长或期望集数时保持 `awaiting_production_specs`，`status` 按此顺序显示当前等待项。用 `set-specs` 分步转录真实选择；新增时长/集数初始化参数无回执会被拒绝；旧路由、总集数或默认值只作待核候选，不猜成已选。三项未齐禁止 treatment/outline 审读及分集、正文。读取当前状态后，只加载本任务需要的上游产物。每个完成的产物单独增加 revision；每集单独提交状态，不把批次当成不可分割事务。

单集状态机：

```text
not_started → planned → draft → in_review → approved
                              ↘ revision → in_review
approved/stale → planned（完成影响分析并获得用户批准后重建）
```

使用 `scripts/update_episode_state.py` 执行迁移。进入 planned/draft/in_review/approved 前，必须有完整规格选择、当前底稿、大纲审读及真实用户对当前版本的确认。实际规划用 `workflow.py PROJECT set-plan --total-episodes N --reason ...` 记录；与期望有偏离时说明剧情理由，不设固定比例，最终随大纲人工确认。批准从当前 batch 报告计算阻断问题，不信任调用者计数；还须最终语义复核、正确的上游 revision 与源文件哈希。`--blocking-issues` 仅保留兼容，手填0不能绕过。

底稿 treatment 绑定规格；outline、batch、final 和大纲确认另绑定实际plan。记录实际总数不无故使已审底稿失效；修改规格仍按其真实依赖传播。

## 上游修改

先运行：

```bash
python3 scripts/impact_analysis.py PROJECT --changed 04-story-bible.md
```

默认只报告直接和间接依赖，不修改项目。向用户说明影响并取得批准后，才加 `--apply`：受影响产物标记为 `stale`，事件追加到失效日志。之后只重建受影响范围，并复跑报告指定的审核器。

不得用更新时间猜依赖，不得静默重写整个项目，不得把未受影响文件顺手改写。锁定决定未解锁时，即使被标记为受影响也只能报告，不能覆盖。

## 旧项目迁移

旧项目缺少 `.drama/` 时，先根据现存文件生成迁移草案，把无法证明的 revision、批准状态和依赖标为 unknown/draft；不得因为文件存在就推断其已批准。旧制作方式、时长和总集数字段只能作为待核候选，不自动生成规格选择回执。用户确认迁移草案后再写入状态文件。


`.drama/workflow.json` 保存阶段、不可变审读会话引用与确认历史；`.drama/readings/READ-*/` 保存分块正文、首读笔记、二遍资料和实际问题报告。正文或其依赖改变即时使门不可通过，`status` 会将已批准受影响集标为 stale；不得因计数为0或文件存在自动恢复批准。详情见 [final-reading.md](final-reading.md)。
