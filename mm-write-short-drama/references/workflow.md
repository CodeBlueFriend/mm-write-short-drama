# 工作流与项目状态

## 目录

- 状态路由
- 阶段产物
- 审核门
- 项目目录
- 变更与交付

## 状态路由

先建立五元路由，并写入 `00-project-brief.md` 和 `.drama/project-state.json`。机器值与加载映射见 [routing-map.yaml](routing-map.yaml)：

| 字段 | 可选值 | 决策影响 |
|---|---|---|
| `source_mode` | 小说改编 / 自主创意 / 近期爆款研究（保留旧素材再创作） | 决定前置拆解流程 |
| `production_mode` | 真人 / AI / 混合 / 暂不限 | 决定制作审核，不改变故事主链 |
| `orientation` | 竖屏 / 横屏 / 自定义 | 决定画面承载与制作审核，不自动改变故事事实 |
| `delivery_scope` | 诊断 / 大纲 / 分集 / 剧本 / 审核 / 改写 / 技巧入库 | 决定本轮终点 |
| `review_mode` | 严格确认 / 辅助确认 / 自动推进 | 决定何时暂停确认 |

严格确认是首个项目默认值。若用户指定当前交付阶段，先把非阻断选择作为 L2/待确认草案写到该阶段，再在下一个审核门暂停；不要因普通缺口让模板保持空白。只有会改变原创/改编路线、主角、核心主题或权利边界的真实阻断项才在起草前询问。辅助、自动与严格模式都必须经过完整故事底稿审读、大纲审读，并等待用户明确确认当前大纲；不得自动确认。各模式只影响其他非阻断节点。

## 阶段产物

0. **任务路由**：项目启动单、缺口和禁区。
1. **需求澄清**：题材、受众、集数/时长、屏幕、情绪、预算、结局、参考维度、授权状态。
2. **材料装载**：仅装当前阶段的事实、技巧、题材和制作规则。
3. **三来源/故事底稿**：按 [source-intake.md](source-intake.md) 登记依据，写到结局的连续底稿，首读复述与来源对照通过才展开大纲。
4. **故事圣经**：世界、人物、关系、声纹、人物弧、秘密揭示、结局和禁改项。
5. **整季结构**：阶段目标、升级、关系、信息、大反转、追看点和结局回收。
6. **分集矩阵**：每集从起始状态经冲突与转折到结束状态。
7. **场次卡**：逐场明确目标、阻力、信息和权力变化。
8. **角色行动模拟**：关键人物基于各自知识和欲望选择策略。
9. **剧本初稿**：每批 3—5 集。
10. **审核返修**：按上游到下游顺序局部返修。
11. **锁定交付**：更新账本、变更日志、版本和上下文包；把本批全部剧集合并导出为一个 Word 文档。

## 审核门

- **A 故事圣经**：变更主角、核心关系、主要对手、世界规则、结局、主题立场时重开。
- **B 大纲**：独立通读通过后，用户明确确认当前版本；机器记录原话、消息定位、时间、范围与源哈希。所有模式均遵守。确认前不得写分集或正文。
- **C 首批分集**：先验证实际节奏和状态变化，再批量生成余下集数。

若用户只要求局部文本，不虚构缺失上游产物。说明依赖缺口，能安全处理则限定范围处理；会改变关键事实则暂停。

## 项目目录

```text
project-name/
├── .drama/
│   ├── project-state.json
│   ├── artifact-index.json
│   └── invalidation-log.jsonl
├── 00-project-brief.md
├── 01-source-index.md          # 改编可选
├── 02-source-truth.md          # 改编可选
├── 03-adaptation-map.md        # 改编项目
├── 03-original-discovery.md    # 原创项目；与上一文件二选一
├── 04-story-bible.md
├── 05-season-architecture.md
├── 06-episode-matrix.csv
├── continuity/
│   ├── canon.yaml
│   ├── timeline.csv
│   ├── character-state.csv
│   ├── knowledge-state.csv
│   ├── relationships.csv
│   ├── props-ledger.csv
│   ├── evidence.csv
│   ├── hooks-ledger.csv
│   └── foreshadowing.csv
├── episodes/
├── deliverables/             # 每批一个合并后的 Word 纯剧本
├── reviews/
├── context-packs/
├── locked-decisions.md
└── change-log.md
```

运行 `python3 scripts/init_project.py <目录> --mode original|adaptation|source-remix` 创建完整骨架，并按需设置 `--production-mode`、`--orientation`、`--total-episodes`。用户本轮只要启动单或故事圣经时，分别加 `--through brief` 或 `--through story-bible`。按阶段校验时使用 `validate_project.py --stage brief|gate-a|full`。

用户明确说“必须、禁止、锁定”的项目要求属于 L0；普通倾向和未审核创作方案属于 L2；通过审核门的故事事实升为 L1。原著事实保留其证据类型，不因为被写入项目而自动成为不可改的项目 L0。

## 变更与交付

变更已锁定事件前，先输出影响分析：直接受影响集数、人物动机、时间线、伏笔、道具、信息状态、待重审范围。批准后做最小范围修改，并在 `change-log.md` 记录日期、原因、旧值、新值、批准者和影响。

影响分析先运行 `scripts/impact_analysis.py` 的只读模式；用户批准后才使用 `--apply` 把依赖产物标为 `stale`。状态与依赖的完整规则见 [project-state.md](project-state.md)。

每批通过后：更新事实与状态账本；记录新增事实；标记伏笔状态；锁定已确认集数；输出审核摘要；为下一批生成上下文包；按 [word-delivery.md](word-delivery.md) 将本批所有集数合并成一个 `.docx`。逐集 Markdown 是内部项目源文件，不能用多个单集 Word 代替合并交付件。


## 当前版本的可执行门

初始化生成 `.drama/workflow.json`。`workflow.py PROJECT status` 恢复真实等待点并持久化失效。`review-pack → first-read → reveal-context → record-review` 依次用于 treatment、outline、batch、final，各会话有原文切块、读者笔记、实读覆盖与内容摘要。`report-template` 只产生空表。大纲 `confirm-outline` 只能转录真实用户决定；新版/旧版哈希不匹配时 `check-writing`、逐集迁移与正式导出都阻断。历史单集 `--blocking-issues` 保留兼容，但不再是批准依据。参考 [final-reading.md](final-reading.md) 完成审稿与退稿。
