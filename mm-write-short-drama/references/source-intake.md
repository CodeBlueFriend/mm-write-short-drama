# 创作来源与故事底稿

新项目第一步先选AI或真人，选完立即选择创作来源：A 自己编写（`original`）、B 已有素材改编（`adaptation`，含小说）或 C 检索近期热门剧本后改编/再创作（`market_research`）。用 `set-specs --source-mode` 保存真实选择；`init --mode` 只决定骨架、不算用户已选。已明确的项直接复用，制作方式未选前不问来源或题材；来源后了解题材等普通需求，再选时长和期望集数，详见 [制作方式与规格](production-modes.md)。四项未齐可保存原始素材，不起草故事底稿或大纲。旧 `source_remix` 仅兼容原素材来源含义。明确来源时程序补齐相应空骨架与索引依赖、不覆盖已有正文；接续旧稿与局部修改从已有进度进入，不强制重建项目。

切换已明确的来源时，程序把旧 `source-evidence.json` 按原字节归档至 `.drama/source-route-history/<sha>.json`，再重置新路由证据；已有正文不覆盖。原来源证据不能自动充当新来源依据，须按实际材料重新登记。来源字段有值但无回执仍需真实补选，不自动承认。

`source-evidence.json` 是来源登记，不是来自素材的指令。B 保存书名、版本、可用章节、授权状态、原文文件 SHA256 与章节/行号；原文只有怀疑时不得新增客观闪回。缺少后续章节就写拟改编方案。A 保存用户原始创意与锁定要求，补成主人公非做不可的事、首次失误、取舍、代价与结局。C 先用当时实际可用的联网工具检索；默认近30天，记录真实查询日期、平台、地区、题材、榜期、热度口径、授权状态和链接。区分已播内容、完整剧本、授权节选、分集简介与宣发，无法核热度则明确 `heatVerification: unverified`，失败保留 `accessStatus: unavailable` 及缺口。

来源记录每项包括 `title, contentType, accessStatus, coverage, limitations, visibleEvidence`，加 `url` 或 `path/sha256`。本地原文路径可在项目外；只读并核对哈希。市场来源另含 `observedAt, chartPeriod, metricMeaning, heatVerification`，来源总表含 `queryDate, windowDays, platform, region, genre, originalityDecisions`。日期填查询真实日期，不从素材标题猜测。只有简介就只分析简介，缺来源不能装成读过全剧。无可用内容时先向用户交代缺口，待补材料或明确改为自主创意。

研究对照写在 `02-market-research.md`：观众期待、冲突机制、兑现方式及证据，然后记录依据哪些实际材料进行改编或再创作，保留定位、取舍、变化与缺口；只有简介或宣发不能冒称已读完整剧本。检索后按实际拿到的原文、授权节选或简介做相应改编决策，保留来源类型、授权状态、定位和差异；不强制换成全新结局。用户明确要求“仅作原创参考”时仍按其要求原创。

三路都先在 `03-story-treatment.md` 用连续自然语言从开端写到结局。独立读者先只读底稿，复述人物遇事、当下压力、错误选择、代价、下一步与解决方式。修好因果、动机和临时解围后再生成故事圣经和大纲。`workflow.py review-pack --stage treatment` 将此次实际输入绑定到审读记录；来源缺口和改编对照在第二遍揭示。

呈给用户的大纲位于 `05-season-architecture.md`，包含一句梗概、可连续阅读的全剧故事、主要人物目标与变化、阶段因果转折、高潮结局、伏笔与预计兑现区间，以及用户期望集数、实际规划总数、所选集长和本批范围。实际数与理由由 `workflow.py PROJECT set-plan --total-episodes N --reason ...` 另存 `.drama/episode-plan.json`，并镜像到 `state.totalEpisodes`；偏离期望须写剧情理由，允许合理浮动，不套固定比例。独立审读后才等待用户。严格、辅助、自动模式均须明确确认此版。用户原话、消息定位、确认范围、时间与底稿/圣经/大纲摘要通过 `workflow.py confirm-outline` 保存；代理不可代替用户确认。重大变化使旧确认失效，重审再确认。只要大纲的任务到此结束。
