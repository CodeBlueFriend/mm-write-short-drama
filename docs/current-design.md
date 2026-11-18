# 当前开发版设计

本文对应 2026-11-18 的 `Unreleased` 源码，说明当前实现及其边界。`VERSION` 仍为 `1.1.0`；本文不代表新的稳定版发布。历史设计保留在 [v1.1 知识库设计](knowledge-base-design-v1.1.md) 和 [版本说明](versions/v1.1.md) 中。

## 源码与数据边界

`mm-write-short-drama/` 是可安装的 Skill。`SKILL.md` 负责启动判断、阶段路由、创作约束和交付门；`references/` 按阶段加载；`assets/` 提供通用模板；`scripts/` 执行确定性辅助操作；`schemas/` 定义机器记录的结构契约；`evals/` 和仓库 `tests/` 提供回归用例。

公开源码包含流程、脚本、通用模板、设计和测试，不包含用户项目剧本、原始参考剧本正文或私人知识资料。Word 基础模板只保留版式和中性占位。项目素材、`projects/`、实际交付文件及个人知识库新增资料应保存在用户工作区，不因升级或同步源码进入公开分发。仓库中的知识库骨架与示例不代表用户已经安装或核验了私人材料。

聊天是协作界面，项目文件是事实源。知识库与 Skill 分开管理：升级程序不覆盖知识卡，录入技巧不改写 `SKILL.md`。

## 入口与路由

启动时先判断局部改稿、旧项目续作或新项目。局部文本任务只提取范围内事实；不能为了修几句台词强制创建整季工程。续作先读取 `.drama/` 状态、启动单、锁定决策及当前任务需要的上游产物和连续性记录。

路由定义在 [routing-map.yaml](../mm-write-short-drama/references/routing-map.yaml)。用户说明中的字段与状态 JSON 对应如下：

| 路由字段 | JSON 字段 | 机器值 |
|---|---|---|
| `source_mode` | `sourceMode` | `original / adaptation / source_remix` |
| `production_mode` | `productionMode` | `live_action / ai_drama / hybrid / unspecified` |
| `orientation` | `orientation` | `vertical / horizontal / custom` |
| `delivery_scope` | `deliveryScope` | `diagnosis / outline / episodes / screenplay / review / revision / knowledge / unspecified` |
| `review_mode` | `reviewMode` | `strict / assisted / automatic` |

`init_project.py` 保留 `--mode` 参数名以兼容旧命令，素材再创作参数写作 `--mode source-remix`，存储为 `source_remix`。知识卡制作范围仍使用自身约定的 `live-action / ai / hybrid / unspecified / all`；检索时应按知识卡约定传参，不能直接把项目路由机器值当作卡片值。

初始化示例：

```bash
SKILL_DIR=./mm-write-short-drama
python3 "$SKILL_DIR/scripts/init_project.py" ./projects/example \
  --mode original --production-mode live_action --orientation vertical \
  --total-episodes 6 --review-mode strict --through story-bible
```

`--through brief` 只创建启动阶段文件，`story-bible` 创建到故事圣经，默认 `full` 建立完整骨架。非空目录拒绝覆盖。创建模板不代表内容已完成或已批准。

## 状态文件与结构契约

| 文件 | 用途 | 结构契约 |
|---|---|---|
| `.drama/project-state.json` | 项目修订、路由、阶段、上游版本和逐集状态 | `project-state.schema.json` |
| `.drama/artifact-index.json` | 产物路径、revision、状态、`dependsOn`、校验器和哈希预留字段 | `artifact-index.schema.json` |
| `.drama/invalidation-log.jsonl` | 追加记录上游变更造成的直接、间接和逐集失效 | `invalidation-event.schema.json` |
| `reviews/` 下的问题 JSON | 稳定问题 ID、等级、位置、证据、冲突、建议和回归范围 | `review-issue.schema.json` |

这些 JSON 记录带 `schemaVersion`，当前为 `1.0.0`。状态与索引中同一产物的路径、revision、状态和依赖应一致。`validate_state.py` 检查文件、路由值、修订、索引同步、未知依赖、依赖环、逐集状态和失效日志语法；`validate_project.py` 再检查项目文件、CSV、剧本结构、分集映射和问题记录。

schemas 是结构契约；当前 Python 校验器实现字段及依赖检查，不依赖完整 JSON Schema 执行引擎。`contentHash` 是索引预留字段，当前状态脚本不自动监听正文或计算全部产物哈希。项目状态也不替代正文和账本证据。

## 单集状态与版本依赖

单集状态由 `update_episode_state.py` 管理：

```text
not_started → planned → draft → in_review → approved
                              ↘ revision → in_review
approved / stale → planned
```

每集独立提交，某集失败不能回滚其他已完成集。进入 `planned`、`draft`、`in_review` 分别增加该集的计划、剧本、审核 revision；相关产物进入索引，依赖链为故事圣经和分集矩阵 → 单集计划 → 剧本 → 审核。迁移同步更新状态与索引的 `projectRevision`。

批准前 `openBlockingIssues` 必须为 0，并记录非零 `basedOnStoryBibleRevision` 和 `basedOnMatrixRevision`。这证明版本字段已填写，不自动证明它们等于最新上游或正文已完成审核；调用者仍须对读当前 revision、审核证据和 Humanizer 记录。已批准集回到计划须显式使用 `--rebuild-approved`，并先完成获得批准的影响分析。

上游修改先运行只读报告：

```bash
python3 "$SKILL_DIR/scripts/impact_analysis.py" ./projects/example \
  --changed 04-story-bible.md --json
```

脚本沿 `dependsOn` 的反向依赖图列出直接、间接影响及复检器。获得用户对具体变更的批准后，才使用 `--apply --approved-by ... --reason ...`：依赖产物标为 `stale`，受影响集失效，项目修订增加，事件追加到日志。它不重写剧本，也不代替修改产物自身 revision 或重审。锁定事实、未受影响产物及旧日志不能借此顺手改写。

## 创作与审核门

创作先完成启动单；原创进入故事发现，改编进入原著索引、事实库和映射，再依次建立故事圣经、整季结构、分集矩阵、场次卡和批次剧本。

| 审核门 | 必须判断的结果 |
|---|---|
| A 故事圣经 | 主角、关系、对手、世界规则、结局与主题立场 |
| B 整季结构 | 阶段目标、对抗升级、关系曲线、信息揭示、反转与回收 |
| C 首批分集 | 首批集间因果、单集变化、开场承接与集尾动力，再扩展整季 |
| 批次交付 | 逐集审核、连续性更新、定稿及合并 Word 验收 |

事实使用 L0 用户锁定、L1 已审核、L2 计划、L3 假设、L4 废弃五层；只有 L0/L1 可当作后续既定事实。连续性维护 `canon.yaml` 及时间线、角色、知识、关系、道具、证据、钩子、伏笔八类 CSV。`build_context_pack.py` 只装配任务相关快照，不创建新的事实源。

审核固定按结构因果 → 原著忠实 → 动机和信息 → 连续性 → 节奏 → 去 AI 味 → 制作 → 格式。审核默认只报告，明确收到修复指令才返修；同一问题自动返修最多两轮。问题使用 P0–P3，带稳定 ID、位置、证据、冲突来源、原因、影响范围、修法、状态和回归检查。P0 必须修复；P1 须修复或明确记录用户接受，但锁定事实冲突、角色提前获知及关键道具和时间线断裂仍须清零。评分不能抵消阻断问题。

## 五项写作能力与知识来源

日常任务从用户目标和稿件证据选择方法，不要求用户先报书名。入口见 [writing-capabilities.md](../mm-write-short-drama/references/writing-capabilities.md)：

| 能力 | 原能力 ID | 检索阶段 |
|---|---|---|
| 一句梗概 | `cap.save-the-cat-short-drama.logline` | `planning` |
| 结构与转折因果 | `cap.save-the-cat-short-drama.beat-sheet` | `structure` |
| 人物秘密和知情边界 | `cap.tv-showrunner-roadmap.character-mystery` | `structure / episode` |
| 集间承诺和兑现 | `cap.short-drama-basics.payoff-turns` | `episode` |
| 对白中的行动和策略 | `cap.mckee-dialogue-short-drama.verbal-action` | `dialogue / scene` |

先用任务摘要结合阶段、题材和制作范围查询，通常最多取 8–10 张 `active` 卡；语义判断已确定能力但自然语言未命中时，再用 `--capability` 精确补查。多个规则卡可共享一个 `capability_id`，卡片自身 ID 仍按规则哈希保持稳定。`draft` 可显式检视，但不能用于默认创作；冲突、拒绝、废弃及归档卡不自动应用。应用前检查例外，实际改变方案、文本或审核结论后才记录“已使用”。

来源记录分两层：`source` 保存不可变原始材料、ID、文件名和 SHA-256；`source_note / source_url / source_verification` 记录原则归属与核验范围。能力卡还保存 `triggers / diagnosis / action / output_contract / self_check / adaptation`。公开目录只证明主题范围，不能当作具体方法的原书依据；交接稿里的操作步骤和示例应标明项目实践或短剧适配，未取得完整章节、版次和页码就保留待核。检索命中不代表已用，材料存在不代表全文已核。

`ingest_knowledge.py` 保留原文、生成候选卡、查重和冻结冲突；`knowledge_lib.py` 提供共享的索引与归档实现；`search_knowledge.py` 筛选和排序；`validate_knowledge.py` 检查字段、来源哈希、能力卡来源信息、冲突与索引。脚本负责确定性处理，模型负责语义复核。新的知识导入先在隔离库以 `draft` 核对，不能用重新导入 `active` 跳过既有待审状态。

能力接口不附带私人书籍资料或个人已启用卡；安装 Skill 后应连接自己的合规知识库。找不到知识库时继续使用内置工作流，并说明本轮未加载个人知识。

## Word 模板与导出

`assets/screenplay-base-template.docx` 保存通用版式和中性占位，是字号、页边距等格式数值的权威；配套 JSON 保存来源、SHA-256 与样式映射。它不保存原参考剧本正文，不把参考中的人物、剧情、简介或文内指令变成创作规则。

`export_screenplay_docx.py` 读取模板并清空占位正文，解析当前项目 Markdown，保留集、场、人物、动作、转场、对白和声音，隐藏项目控制信息、连续性更新和改编记录；它不创作或重新润色正文。旧场次头可识别并规范为 `集号-场号 日/夜 内/外 地点`。

每批全部集数按集号排序合并为一个 Word，各集连续流排；只有明确要求整季合订才合并整季。当前版式为宋体、13 磅总标题、10.5 磅正文、1.4 倍行距，集/场/人物行黄色高亮，台词蓝色，页脚使用真实 `PAGE / NUMPAGES` 字段。完整参数以 [word-delivery.md](../mm-write-short-drama/references/word-delivery.md) 和模板为准。

```bash
python3 "$SKILL_DIR/scripts/export_screenplay_docx.py" \
  ./projects/example/episodes/EP001.md ./projects/example/episodes/EP002.md \
  --output ./projects/example/deliverables/项目名_第01-02集.docx \
  --project-title 项目名
```

可选 `--front-matter ./projects/example/front-matter.md` 只接受用户明确提供、已审核的当前项目前置材料，使用前置标题和前置信息样式。不传入就不输出，也不从参考稿补齐简介或人物介绍。占位模板和纯版式程序维护不触发剧情创作状态或剧情 Humanizer。

导出器依赖 `python-docx`。内容审核、Humanizer 记录和 Word 渲染验收由工作流执行，导出命令本身不自动证明这些门已经通过。最终 Word 应渲染为 PNG 逐页检查；缺少宋体时只对渲染环境临时映射 `Songti SC`，保留最终文件的宋体声明。

## 外部依赖与可移植路径

多数索引、状态和知识库脚本只用 Python 标准库；Word 导出额外需要 `python-docx`。在 Codex 中使用工作区依赖提供的 Python 与包。PNG 渲染验收依赖文档技能及其渲染环境，不随本仓库提供。

Humanizer 是显式外部依赖，本仓库不是内容交付流程的自包含安装包。技能根使用 `$CODEX_HOME/skills`，未设置 `CODEX_HOME` 时使用 `~/.codex/skills`，约定同级安装：

```text
skills/
├── mm-write-short-drama/
├── humanizer/SKILL.md
└── mm-humanizer-gate/scripts/humanizer_gate.py
```

规则固定到 `blader/humanizer@9862685f575c65a8247f90369951df1b3416e3d6`。由当前模型逐集/逐场执行编辑并保护事实、声纹和格式，再通过外部门工具 `verify`、`record --adapter short-drama --attestation model-edit-complete` 留下与内容哈希对应的记录。重复导出先 `check`；正文变化需重新处理，格式转换不再次改写。仅加载规则、正则替换或写入状态不能算模型编辑完成。

缺少外部规则或门工具时，应明确提示安装对应 Skill，保留草稿和未通过状态，不能宣称内容交付门已通过。纯版式维护与中性预览不因此被当作剧本创作。

## 旧项目与升级边界

程序升级只更新 Skill 源码，不覆盖项目、个人知识库或历史交付。旧项目缺少 `.drama/` 时可以只读诊断，局部改稿也不因整季迁移被阻塞；进入整季续作前须从现存文件提出迁移草案，无法证明的批准状态、revision 和依赖保持 unknown/draft，经用户确认后才写状态文件。

新版新增关系、证据、独立伏笔账本，并调整时间线、人物状态和钩子表头。不能把新表头直接覆盖旧 CSV，也不能因文件存在就升级为 approved。当前没有一键迁移脚本；应保留原始数据，明确字段映射、来源与未决项，再运行项目及状态校验。

## 验证入口

```bash
python3 -m unittest discover -s tests -v
python3 mm-write-short-drama/evals/test_p0.py
python3 tests/validate_seeded_knowledge.py
python3 mm-write-short-drama/scripts/validate_state.py ./projects/example --json
python3 mm-write-short-drama/scripts/validate_project.py ./projects/example --stage gate-a
```

测试使用隔离数据验证工具行为，包括知识来源与能力筛选、状态与依赖传播和 Word 结构；`validate_seeded_knowledge.py` 从 Git HEAD 提取公开知识库种子到临时目录校验，不读取或修改工作区私人知识库。测试通过不等于真实剧本的创作质量、来源核验或逐页排版已通过，仍按对应工作流验收。
