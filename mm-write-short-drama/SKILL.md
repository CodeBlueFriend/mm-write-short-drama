---
name: mm-write-short-drama
description: 分阶段创建、改编、续写、审核和去 AI 味短剧剧本，把每批全部集数合并为一个 Word 文档交付，并用项目文件维持人物、时间线、信息、道具和伏笔连续性，按当前阶段检索独立的个人编剧知识库。适用于从一句创意、人物、故事、小说、梗概或真实事件建立真人短剧、AI 真人剧或 AI 漫剧项目；设计故事圣经、整季结构、分集矩阵和场次卡；分批写完整剧本；检查跨集矛盾、原著忠实度、对白声纹、制作可行性；继续已有短剧项目；把用户粘贴或放入 inbox 的编剧技巧保存原文、提炼为知识卡、分类、查重、查冲突、检索和调用。不用于单纯小说润色、分镜或图片/视频提示词、剪辑配音、行业新闻和平台政策查询。
---

# 短剧编剧

把聊天视为协作界面，把项目文件视为唯一事实源。按“先决策、后扩写；先结构、后措辞；局部返修优先”的顺序工作，交付可进入制片或分镜环节的剧本。

## 启动任务

1. 检查工作区是否已有短剧项目文件。续作时先读取 `.drama/project-state.json`、`.drama/artifact-index.json`、`00-project-brief.md`、`locked-decisions.md`、当前任务依赖的上游产物、相关连续性账本和最新变更记录，不凭聊天记忆续写。缺少新版状态文件的旧项目可继续只读处理；整季续作前先说明并迁移，不猜测状态。只改用户提供的局部文本时，从稿件摘取必要事实并限定范围，不以全项目迁移阻塞改稿。
2. 路由任务：`source_mode`（原创/改编/素材再创作）、`production_mode`（真人/AI/混合/暂不限）、`orientation`（竖屏/横屏/自定义）、`delivery_scope`（诊断/大纲/分集/剧本/审核/改写/技巧入库）、`review_mode`（严格确认/辅助确认/自动推进）。机器值与加载规则见 [routing-map.yaml](references/routing-map.yaml)。
3. 新项目先用 `scripts/init_project.py` 创建目录；用户已限定本轮阶段时用 `--through brief|story-bible`，避免提前创建下游空文件。再填写项目启动单。改编项还要确认素材位置、来源和授权状态；只记录授权声明，不代替法律判断。
4. 只追问会改变结果的关键缺口，一次最多三项。其余标记为“待定”，不得偷偷固化。
5. 按当前阶段读取资源，不要一次加载全部参考资料或全部原著。
6. 优先读取项目启动单中的“个人知识库路径”，否则从当前工作区向上查找 `knowledge-base/`；按 [knowledge-base.md](references/knowledge-base.md) 用同一命令检索内置卡与可选个人知识库。找不到个人库时直接检索随技能安装的内置卡。

## 选择路线与资源

- 所有项目：读取 [workflow.md](references/workflow.md)。
- 状态恢复、单集迁移、上游修改或失效传播：读取 [project-state.md](references/project-state.md)。
- 原创发现：再读取 [original-creation.md](references/original-creation.md)。
- 小说或素材改编：再读取 [adaptation.md](references/adaptation.md)；先运行 `scripts/index_source.py` 建索引。
- 故事圣经、整季结构、分集矩阵：读取 [story-structure.md](references/story-structure.md)。
- 场次卡、角色推演、剧本和对白：读取 [scene-and-dialogue.md](references/scene-and-dialogue.md)。
- 续写、跨集修改或审核：读取 [continuity.md](references/continuity.md)，必要时运行 `scripts/build_context_pack.py`。
- 去 AI 味或台词改写：读取 [anti-ai-style.md](references/anti-ai-style.md)。
- 真人/AI/混合制作风险：只在用户指定或请求评估时读取 [production-modes.md](references/production-modes.md)。
- 审核、返修或交付：读取 [review-rubrics.md](references/review-rubrics.md)，并运行 `scripts/validate_project.py` 与 `scripts/screenplay_stats.py`。
- 生成剧本 Word 交付件或维护其版式：读取 [word-delivery.md](references/word-delivery.md)，默认使用 [基础 Word 模板](assets/screenplay-base-template.docx)，运行 `scripts/export_screenplay_docx.py`，再按其中的渲染门逐页检查；模板仅提供格式，不提供剧本内容。
- 录入、检索和运用个人技巧：读取 [knowledge-base.md](references/knowledge-base.md)。知识卡规范见 [techniques-catalog.md](references/techniques-catalog.md)，对话或批量录入细节见 [techniques-inbox.md](references/techniques-inbox.md)。

## 分阶段检索编剧知识

日常梗概、结构、秘密揭露、相邻集卡点、对白改稿，以及“教我写/给我练一题”，先按 [五项写作能力](references/writing-capabilities.md) 从原文证据定位问题，再用下述检索入口选已启用卡。用户无需指定书名。局部任务先交范围内可用稿，纯润色不改锁定剧情，无隐瞒驱动的戏跳过秘密方法；教学才采用诊断、示范、复练。书籍原则、公开目录主题与交接包项目实践分开归属，不将检索命中或材料存在报告成已应用或已核全文。

在开始生成当前阶段产物前运行 `scripts/search_knowledge.py`，只装配匹配任务的少量 `active` 卡片。内置卡可直接使用。同能力有匹配任务的已启用个人卡时，优先采用个人卡：

- 故事发现、故事圣经：`--stage planning`；
- 整季结构：`--stage structure`；
- 分集矩阵、开场、卡点：`--stage episode`；
- 场次卡和行动设计：`--stage scene`；
- 对白、潜台词、去 AI 味：`--stage dialogue`，审核时可再查 `review`；
- 小说拆解与改编映射：`--stage adaptation`；
- 多轮审核和制作检查：`--stage review`。

同时传入当前题材与制作形式，并用一句任务摘要作为查询词；默认最多取 8—10 条。不要读取整个 `cards/`。当前项目明确要求、锁定事实、安全与版权硬约束优先于知识卡；卡片例外命中时不应用；`draft`、`pending-conflict`、`rejected`、`deprecated`、`archived` 一律不得自动应用。把本轮真正影响创作或审核的规则 ID 记录在审核报告，不能把“检索到”冒充“已使用”。

## 执行状态机

按以下顺序推进；若用户只请求某一阶段，仍先验证它依赖的上游文件：

1. 输出并保存项目启动单，同时更新 `.drama/project-state.json`；产物完成与否以文件、状态和校验结果为准，不以聊天中的口头声明为准。严格确认模式允许把非阻断选择作为 L2/待确认草案写到用户指定阶段，然后在下一个审核门暂停；只有会导致路线根本不同的真实阻断项才在起草前询问。
2. 原创时完成故事发现；改编时完成原著事实库与改编映射。
3. 建立故事圣经。主角、核心关系、主要对手、世界规则、结局和主题立场须通过审核门 A。
4. 建立整季结构。阶段目标、对抗升级、关系曲线、信息揭示、大反转和回收计划须通过审核门 B。
5. 建立分集矩阵；先审核首批分集再扩展整季，通过审核门 C。
6. 写场次卡，对关键场景按人物已知信息、即时欲望、恐惧和策略做行动推演。
7. 默认每批写 3—5 集，不一次生成长季全剧。每场至少改变一项事实、关系、资源、信息、情绪策略或风险状态。
8. 固定按结构因果 → 原著忠实（改编）→ 人物动机与信息 → 连续性 → 节奏 → 去 AI 味 → 制作 → 格式审核。审核默认只报告，不擅自改稿；收到明确修复指令后才进入返修。
9. 先修上游问题，再修措辞。自动返修同一问题最多两轮；仍未通过则交用户裁决。
10. 单集按 `planned → draft → in_review → revision/in_review → approved` 推进，使用 `scripts/update_episode_state.py` 记录逐集状态；批量任务逐集提交，某一集失败不得回滚已完成集。通过后更新全部相关账本、变更记录和锁定状态，生成下一批上下文包，并把本批所有集数按顺序合并为一个 `.docx` 交付件。

## 强制约束

- 将事实分为 L0 不可变、L1 已确认、L2 当前计划、L3 临时假设、L4 废弃。只有 L0/L1 能作为后续既定事实引用。用户明确说“必须/禁止/锁定”的项目要求记为 L0；普通偏好与未审核创作方案先记 L2；通过审核门的创作事实升为 L1。
- 改编内容明确标注“原著事实、合理推断、改编决定、待确认项”，重大改编记录来源、原因和影响范围。
- 修改锁定内容或已批准上游产物前，先运行 `scripts/impact_analysis.py` 生成只读影响报告，列出直接/间接依赖、受影响集数和复检范围；等待用户批准后才用 `--apply` 标记失效并局部改写。不得静默全量重写。
- 关键创作选择只提供最多三种有明显差异的方案。不得泛化模仿在世作者或单一作品的独特风格；把参考作品拆成可借鉴维度。
- 心理尽量转成可见动作、停顿、选择和对白。对白服务人物行动，不用双方已知信息向观众作完整说明。
- 不用突然降智、无来源巧合、机械偷听/撞见或无状态变化的口头胜利代替因果。
- 去 AI 味先校准动机和信息，再处理潜台词、声纹、动作和节奏；不得靠随机语气词、方言、错字或流行梗伪装真人感。
- 制作审核报告风险和替代呈现，不得未经授权为“好拍/好生成”删除戏剧核心。
- Skill 工作流与 `knowledge-base/` 分开管理。升级 Skill 不覆盖个人知识；录入知识不改写 `SKILL.md`。
- 原始资料永不删除。新规则不得覆盖同 ID 或旧版本；重复项只记日志，冲突项保持 `pending-conflict`，直到用户明确裁决。

## 审核与交付

原有审核和返修通过后、任何聊天返回、Markdown 保存或 Word 导出前，必须执行 [Humanizer 适配规则](references/humanizer-adapter.md)：保存草稿，读取本 Skill 随附的 [Humanizer 固定版规则](references/vendor/humanizer.md)，由当前模型逐集/逐场执行编辑，再复核剧情信息、角色声纹、场次格式与连续性。读取规则、正则替换和填写状态都不算完成。失败时保留草稿并维持 `in_review`/`revision`，不得推进到 `approved`。

文件交付使用本 Skill 随附的 `scripts/humanizer_gate.py` 执行 `verify` 和 `record --adapter short-drama --attestation model-edit-complete`；导出前用 `check` 复用同一已处理版本。正文变化后哈希失配，必须重新处理。Word 只从验证成功的定稿 Markdown 生成，格式转换不再次改写。

对每个问题给出：稳定 ID、位置、证据、等级、冲突来源、原因、影响范围、建议修法、状态和回归检查范围；结构见 `schemas/review-issue.schema.json`。审核报告增加“实际使用的知识规则 ID”和“不适用/被项目要求覆盖的规则”。P0/P1 必须为 0 或由用户明确接受；锁定事实冲突、角色提前获知、关键道具和时间线断裂必须为 0；重大改编必须有记录。评分只用于排序，不能抵消阻断问题。

交付至少包括定稿剧本、连续性更新和审核摘要。项目目录内继续维护含“控制信息/连续性更新”的逐集 Markdown 项目版；面向用户交付隐藏这些维护字段的演员/制片纯剧本 Word 版。

剧本 Word 版遵循以下硬规则：每次交付只生成一个 `.docx`；本批写了多少集，就把多少集按集号顺序合并进去，不得拆成“一集一个 Word”；各集连续流排，不强制下一集另起一页。文件名使用“项目名_第起始集-结束集.docx”，单集则使用“项目名_第NN集.docx”。若用户明确要求整季合订本，才合并全部已确认集数。默认使用 `assets/screenplay-base-template.docx` 的版式，导出前清除模板占位；只有明确提供且已审核的当前项目前置内容才通过 `--front-matter` 输出。版式与字段取舍以 [word-delivery.md](references/word-delivery.md) 为准。

纯版式模板维护、导出程序修改和中性占位预览不触发剧情 Humanizer 或逐集创作状态迁移，仍须核对格式并渲染验收；真实正文的审核与 Humanizer 要求保持不变。

## 脚本约定

所有脚本仅负责初始化、依赖传播、状态迁移、上下文装配、字段校验、统计和文档导出，不用程序分数替代创作判断。状态 JSON 必须带 `schemaVersion`；上游 revision 改变后，下游在重新审核前保持 `stale`。知识库脚本只做确定性提取、启发式分类/冲突提示和检索；Codex 仍须语义复核知识卡。先运行 `python3 scripts/<name>.py --help` 查看参数；模板位于 `assets/`，复制后再填写，不直接覆盖模板。生成 `.docx` 时按 [Word 交付规则](references/word-delivery.md#准备-word-导出环境) 选用工作区 Python 或在项目内准备独立导出环境，按当前环境支持的渲染方式逐页检查。
