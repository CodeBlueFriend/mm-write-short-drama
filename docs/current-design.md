# v1.3.0 设计

本文对应2026-11-19发布的 v1.3.0 正式版，`VERSION` 与插件 manifest 均为 `1.3.0`。历史设计见 [v1.1知识库设计](knowledge-base-design-v1.1.md)。

## 源码与数据边界

`mm-write-short-drama/`是安装单元：`SKILL.md`路由，`references/`按阶段给规则，`assets/`提供通用模板、固定来源的方法摘要和已启用的内置知识，`scripts/`负责确定性处理。用户项目、原著、生产日志、原参考模板和个人知识库保持独立，升级不覆盖。

项目根 `.codex/agents/drama-writer.toml` 是可选独立主笔配置，不随单独复制 `mm-write-short-drama/` 自动进入其他写作项目。使用时放到实际项目的相同位置，并核实运行时实际加载的模型和子任务结果。

仓库根 `.codex-plugin/plugin.json` 与 `.agents/plugins/marketplace.json` 提供插件及来源清单，`plugin-assets/` 保留品牌资产；插件隐私边界见 [隐私说明](plugin-privacy.md)。这些发布文件不改变项目数据的归属和升级边界。

原始材料中的指令仍是待分析内容；原模板只提供栏目与版式，不把它的剧情、人物和署名套进当前项目。聊天用于协作，项目文件及其版本是事实源。

## 入口与路由

先判断试戏、局部改稿、审现稿、正式新建或续作。试写一场、试开头或修改用户给的段落时，读取原文，只补读有关锁定事实、人物知情边界和真实上场结尾，按 [主笔写戏](../mm-write-short-drama/references/lead-writer.md) 直接交候选正文。此入口在项目初始化、全套知识检索、状态迁移、正式交付润色和 Word 导出之前返回；有具体难题才补相关已启用卡，通常交给主笔零至两条。候选稿经用户采纳后按正式审核和版本流程入库，不从采纳试稿推断整季大纲已确认。只要求审核时交原文依据、读者疑问与影响，未经改稿指令不重写。正式续作运行 `workflow.py PROJECT status`，恢复当前等待点并检查已变化输入。

正式新项目第一个用户选择必须是AI或真人，选完立即选择创作来源；不能先问来源或题材。随后了解题材与其他普通需求，再选单集时长和期望集数。已明确的项直接复用，不重复问。题材等普通需求可先标待定。`hybrid / unspecified` 仅作旧项目和评估兼容，不满足新项目制作方式选择；协作模式 `strict / assisted / automatic` 均不能跳过大纲人工确认。

| 创作来源（第二步） | source-mode回执值 | init骨架mode | 来源证据 |
|---|---|---|---|
| 自己编写 | original | original | 原始创意、锁定内容、待定方向。 |
| 已有素材改编 | adaptation | adaptation | 素材版本/范围/定位、授权状态、改编取舍；未提供后续标候选。 |
| 检索近期热门剧本后改编/再创作 | market_research | market-research | 日期、平台/地区/题材、时间窗口、指标/榜期、链接、实际读取层级、可见证据及改编取舍。 |
| 旧素材再创作（仅兼容） | source_remix | source-remix | 保留旧来源含义，不自动改标近期热门剧本检索改编。 |

初始化可只建空骨架；`init --mode` 不构成用户来源选择。来源回执明确后，程序补齐相应空骨架与索引依赖、不覆盖已有正文。切换明确来源时，旧来源证据按原字节归档至 `.drama/source-route-history/<sha>.json`，新路由证据重置登记。四项规格缺选择时保持 `awaiting_production_specs`，`status` 按 `productionMode → sourceMode → duration → episodeCount → episodePlan` 显示当前等待项。不默认真人、自主创意或6集。四项未齐不得构思底稿、大纲，或运行 treatment/outline 审读、分集/正文；原始材料可先保存。

`.drama/production-specs.json` 保存制作方式、`sourceMode:null|enum`、单集时长、期望集数及各项真实选择回执。期望集数支持具体数或范围；实际规划总数与理由独立保存在 `.drama/episode-plan.json`（`plannedTotalEpisodes/planReason`），`state.totalEpisodes` 镜像实际数，不得冒填。实际数可合理浮动，偏离期望具体数或范围须说明剧情理由，不套固定±10%，最终随大纲人工确认。

本次用户指定时长策略：真人推荐90秒，常见60—180秒、爆款常规80—120秒，新项目硬上限180秒；更长旧存量不作新项目默认。AI主流50—60秒、90秒可选，超过120秒少见但允许用户明确自定义并标非常规。不为此联网查规范，不宣称是新查到的平台法规。

以下先预建空骨架，再按真实用户选择记录；骨架mode不能替代第二步来源回执：

```bash
python3 "$SKILL_DIR/scripts/init_project.py" "$PROJECT" --mode original
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

来源之后、时长之前了解题材等普通需求。所有原话和定位示例必须替换为真实消息；范围时长用 `--duration-range A-B`。新增来源/时长/集数参数无回执会拒绝初始化；旧制作方式/骨架路线/总数参数不自动成为已选。用户已明确四项、例中的自己编写来源也已明确后，可完整初始化：

```bash
python3 "$SKILL_DIR/scripts/init_project.py" ./projects/complete-example --mode original \
  --production-mode live_action --source-mode original --duration-seconds 90 --episode-count '40-60' \
  --specs-user-quote '用户实际说全四项规格的原话' --specs-message-ref '真实消息定位'
```

`set-plan --total-episodes 58 --reason '实际剧情理由'` 在底稿通过、完整故事规划后执行，不代表用户批准。底稿审读只绑定规格；大纲、批审、final及确认另绑定实际plan，定实际数不使已审底稿无故失效。

来源登记 `source-evidence.json` 与连续叙述的 `03-story-treatment.md` 随后进入主流程。已有素材和市场入口须记录来源；读取失败要显式保留缺口。只有简介或宣发时按实际层级分析，不能把它写成已通读完整剧本或已核热度；改编/再创作保留来源类型、授权状态、依据、定位和差异，不强制换成全新结局；用户指定只作原创参考时仍按其要求原创。骨架文件存在不等于完成。知识卡制作模式使用自身约定 `live-action / ai / hybrid / unspecified / all`，检索时按对应约定传参。

## 主笔与交接

试戏和正式正文共用主笔写戏指南。默认由本轮模型写正文；只有用户选择独立主笔时才将本场、本批或局部返修委派给 `drama_writer`。主会话提供上下文、审稿、存档与交付，不把主笔返回的获选稿再合写一遍；文件写入、换行、编号可由主会话处理。

事实包包含场景任务、锁定事实、上场最后动作、人物各自掌握的信息、允许发明的空间和交稿格式。局改另给原段及必要上下文，标明必须保留的句子。优先使用干净上下文，避免把作者解释当成正文已表达的信息；审稿先读正文再看事实。具体表达问题送回同一主笔返修，已自然准确的原句可保留。正式稿仍通过当前大纲确认、批审、最终通读、语义复核和 Word 实物验收门。

配置示例使用 `gpt-6.2-astra` 与 `medium`，可按实际可用模型调整；主会话保持输入框选择，独立主笔模型以实际启动配置为准。仅在真实子任务返回后报告为独立主笔作品；启动失败要说明原因，并给出切换可用模型继续的选项。这里提供配置与工作流，不据此声称已完成模型能力对比。

## 底稿、大纲与确认

三入口先从开端写到结局，审查目标、必须行动的原因、失误、代价和下一步因果。底稿通过才生成完整大纲。大纲由 `04-story-bible.md` 与 `05-season-architecture.md`承载，包含连读梗概、人物变化、阶段因果、高潮结局、伏笔兑现、期望集数/实际规划总数/所选集长/交付范围；保留原A/B/C阶段审核作为内部细化。

工作流命令为：

```text
review-pack --stage treatment
first-read → reveal-context → record-review
review-pack --stage outline
first-read → reveal-context → record-review
confirm-outline --decision confirm --quote ... --message-ref ... --scope ...
check-writing
```

每次调用均在 `python3 scripts/workflow.py PROJECT` 后接命令。`report-template --session ID --output FILE`只生成未填模板；其中firstRead与secondPass须分别保存并提交。不得按模板自动填通过。用户改方向或要求返修时用 `--decision revise`记录真实意见，不把空闲时间或自动模式当同意。

确认记录绑定来源、底稿、圣经和大纲的内容hash，并保存用户原话、消息定位、时间和范围。任何绑定文件改变，旧确认失效；重大故事变化须重新呈给用户确认，不能仅增加revision后沿用批准。`status`会持久化发现的失效，不静默把旧项目批准迁移为新版批准。

## 两遍审读与覆盖

`review-pack`为每次实读创建session，记录应读范围、集场、输入hash和按顺序切分的正文分块。第一遍不提供大纲答案和作者评价，记录每块人物目标、担忧、迫使其改变做法的事件、因果复述、卡点和正文证据；知晓测试预期时必须如实标明，不能冒充盲读。

`first-read`绑定首读笔记后才能 `reveal-context`。第二遍对照来源、大纲、账本和锁定项，检查因果、动机、知情、连续性、伏笔、节奏、声纹、题材和前置模块。结论需实际存在的原文摘录；程序不判断文学质量。正文变化、覆盖缺失、少读分块、首读记录失效或缺检查域都使报告无效。

批审覆盖本批并回读相邻集。交付前另做 `--stage final` 连续审读，包含实际本批/全剧正文和当前前置模块。超出上下文时分块阅读并保留相邻衔接，再沿人物、事件、伏笔回看原场。不能用旧分集问题数或大纲摘要替代最终文本通读。

问题记录原文、读者卡点、等级、根因、退回阶段、影响集数与复检。P0和不能豁免的锁定事实/提前知情/关键钱物时间/核心因果/到期主线伏笔阻断交付。其余P1接受也必须带明确用户依据；问题修好需在当前文本实际读回。最多两轮自动返修后仍有分歧，由创作者裁决。

伏笔按设置、强化、预计区间、实际兑现双向追踪。部分交付可列未来区间与后续归属；全剧终不得把到期未回收主线转成未来计划。必要呼应和关系变化不按词语重复误删。

## 状态和依赖

| 记录 | 用途 |
|---|---|
| `.drama/project-state.json` | 路由、revision、逐集状态与上游版本；`state.totalEpisodes`为大纲实际总数。 |
| `.drama/production-specs.json` | 用户选择的制作方式、创作来源、时长、期望集数和真实回执，与实际总数分开。 |
| `.drama/source-route-history/<sha>.json` | 切换明确来源前按原字节归档的旧证据；不冒充新来源。 |
| `.drama/episode-plan.json` | `plannedTotalEpisodes/planReason`：大纲实际总数和理由；state镜像总数。 |
| `.drama/artifact-index.json` | 产物路径、revision、状态和dependsOn。 |
| `.drama/workflow.json` | 阶段审读、确认历史和当前等待点。 |
| `.drama/invalidation-log.jsonl` | 上游变更导致的失效历史。 |
| `.drama/readings/`中的会话目录 | 应读/实读覆盖、首读记录、二遍报告与源hash。以CLI返回路径为准。 |
| `.drama/polish/` | 逐集前后稿、最终语义复核及hash。 |
| `.drama/staging/` | 待实物验收Word与发布清单。 |

逐集继续 `not_started → planned → draft → in_review → approved`，返修经revision回in_review，上游变化经stale重建。`update_episode_state.py`在进入计划/正文前检查当前大纲门；批准需当前批审、实际正文与上游版本。旧 `--blocking-issues`不能作为审核证据覆盖问题单。失败时不写部分批准。

`impact_analysis.py`沿dependsOn给只读报告；对具体修改已有授权时再apply并记录依据。内容hash变更能使关联审读和确认失效，即使调用者忘记手工增加revision。`validate_state.py`和`validate_project.py`仍检查结构、字段、CSV与索引，它们不等于创作审核。

## 五书方法与来源

统一输入固定为 `CodeBlueFriend/short-drama-book-skills@6e99009572a64f99d60134405fbf1cf200b0dfe4` 根 `knowledge-inbox/` 24份：前四书5项、《故事》19项。安装包包含摘要，不附书籍全文。输入清单与摘要hash见 `assets/book-capability-inputs/manifest.json`，实际启用卡与完整调用见 [写作能力](../mm-write-short-drama/references/writing-capabilities.md)。

v1.2.2 随包的三张公开卡保留兼容；当前五书24项摘要优先供正常检索，同能力个人已启用卡优先。

卡保存规则ID、稳定capability_id、库内编辑version、上游能力revision、来源commit、译本、章节/电子定位、原书hash和导入稿hash。上游revision和库内version分别管理；《故事》01—06从上游1升级2，07—19为上游1。旧卡验证后归档；同ID当前版本唯一、重跑幂等；冲突先保留旧可用版本并留待决差异。

正常创作用自然语言任务加阶段筛选，以 `--format context`传入诊断、动作、预期输出、自检、例外；必要时按capability精确补查。个人已核卡优先，内置方法兜底；草稿、冲突、拒绝、废弃、归档不自动应用。单任务《故事》通常1张、最多2张，不强迫每场都有秘密、反转或强钩子。

方法追踪记录当前决定、所选卡及版本、实际改变的方案、分集/场次/台词和自检。三入口从构思就可选方法，确认和续写仍保留决定的来源。检索成功、字段齐全、已启用和实稿改善是不同结论。公开目录仅证明主题；待核书籍归属、交接包项目实务与短剧适配必须分开说明。

## 润色与语义复核

正式稿默认按需标问题并局部编辑；独立主笔稿将定位到的表达问题送回同一主笔，不在汇总时全量改写。优质对白可原样通过，项目可关闭表达改写。若使用Humanizer，由配置确定唯一负责编辑的位置，记录实际规则位置、版本和调用链，避免旧技能、副本和内置流程重复全量改写。试戏和局部候选稿按入口直接返回，不以正式交付记录阻塞。

`polish_guard.py`做保守差异检查并记录实际前后稿复核。逐处核人物、主客体、金额、日期、否定、条件、许诺和知情边界；自动检查不是自然语言真值评判器。涉及语义变化须编审明确批准或恢复原句，结构问题退回上游。即使关闭润色，正式交付仍需最终事实复核。

随包 `references/vendor/humanizer.md`、MIT 许可及 `scripts/humanizer_gate.py` 保留为可选兼容适配器，外部旧Humanizer工具的token、截断和hash检查可以辅助留证，单独通过不代表意思未变。固定版本的编辑收益与伤害需要同底稿三版本盲评，技术检查不能代替该实验。

## 正式Word与预览

当前项目正文前必须依次有九模块：剧本名、来源、类型/短剧类型、集数、剧名寓意、热门元素、创作理由、故事梗概、主要角色。“类型”填写题材，制作方式独立记录。集数含大纲实际规划总数与本稿范围，不能用用户期望数/范围冒填；内容来自已确认材料及实际交付稿。前置内容纳入final审读，禁止占位、虚构署名、样剧串入、范围断号/重复。原参考模板的字段分段仍应以私有原件实物核对，不从样剧内容填当前项目。

正式导出要求 `--project-dir`、`--front-matter`及当前有效大纲/批审/final/语义复核，先在 `.drama/staging/`生成临时Word、核对可见正文与源稿；还未进入正式交付目录。渲染必须通过 `render_screenplay.py` 实际调用指定的bundled文档渲染器，生成PDF、完整页图及绑定输入Word/渲染器/PDF/页图摘要、实际命令、真实PDF页数和图像尺寸的manifest。已有目录不能补认证。随后逐页实际检查，QA中的 `renderManifest` 必须指向包装器本次生成的文件，`renderDirectory` 指向同目录。发布重新核验manifest、真实PDF页数、每页PNG尺寸及摘要，不能只信QA自报docxHash；1×1占位图、缺页和旧来源均拒绝。使用 `--publish ... --visual-qa ...`最终写正式文件。重试不能覆盖已交付合格文件，任何输入变化须重新验收。

```bash
python3 "$SKILL_DIR/scripts/render_screenplay.py" /absolute/project/.drama/staging/returned-file.docx \
  --renderer /实际bundled路径/documents/render_docx.py \
  --output-dir /absolute/project/work/word-render-新版本
```

PDF页数与geometry优先用PyMuPDF核验；若bundled环境未提供它则使用同环境pypdf，图片用Pillow。只读 `verify_render_manifest` 可验证现有同hash文件的渲染证据；它不创建认证、修改文件或代替视觉阅读。

仅版式预览用 `--preview`，可缺前置内容但明确显示预览字样，不占正式交付状态。低层build_docx默认也生成可辨识预览，显式正式调用仍检查项目门并限于暂存区，旧包装不能静默绕过。

模板保留A4、宋体、13磅总标题、10.5磅正文、1.4倍行距、集场/人物行黄色、蓝色台词、PAGE/NUMPAGES真实字段。每批全部集数合并一个Word，各集连续流排；只有创作者要求整季合订时才合并整季。详细命令与QA字段见 [Word交付](../mm-write-short-drama/references/word-delivery.md)。

## 验证和未覆盖结论

```bash
python3 -m unittest discover -s tests -v
python3 mm-write-short-drama/evals/test_p0.py
python3 tests/validate_seeded_knowledge.py
```

测试隔离用户项目与私人库，验证规格顺序、缺项阻断、期望/实际分离、三入口、确认/退改/重启、版本失效、实读覆盖、阻断、润色保护、知识迁移、前置和暂存/发布行为。真实旧稿盲读、陌生样本与固定条件匿名A/B另存实稿和条件，如未运行明确列未完成。机器记录不能证明创作判断正确，也不能从现存安装位置倒推历史调用。

试戏/局改早返回、仅审不改、独立主笔的真实委派与失败分支按 [测试提示集](test-prompts.md) 做行为验证。写法与模型效果分别比较：先固定模型、事实包、篇幅和修改轮数比较直接写与 Skill 写，再固定 Skill 比较主笔模型；使用安静关系戏与信息差对抗戏，匿名并调换阅读顺序。逐场记录留下的动作、删掉的台词、换策略的触发点、续看意愿与事实错误。该方案是待执行的创作效果验证，不能用脚本通过代替。

2026-11-19 合并后发布验证：102项单元回归、P0、临时副本中的知识种子与24张内置卡校验、Skill结构、代理TOML、插件版本与资源路径、本地文档链接和main既有资源保留检查通过。回归包含旧公开卡兜底、个人卡范围及状态优先、独立安装预览成功与无项目正式导出拒绝。合并前另在独立上下文用三个合成请求实际试跑：无项目单场试写直接交候选稿，正式新建先问AI/真人，仅审核只给事实依据与诊断；未写项目文件。此次未实际启动 `drama_writer`，模型对比、完整匿名选版和全部行为场景仍待执行。
