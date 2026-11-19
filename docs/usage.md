# v1.3 命令行使用手册

以下命令从仓库根目录运行。直接在 Codex 对话里立项、续写或审稿，可从 [项目首页](../README.md) 选择示例。独立试戏、局改和仅审核使用主入口直接返回候选结果，无需初始化或经过下述正式交付门；采纳后再按正式项目流程纳入。

## 知识库命令

### 日常录入一条技巧

用户已经确认、准备直接启用时：

```bash
python3 mm-write-short-drama/scripts/ingest_knowledge.py \
  --kb ./knowledge-base \
  --text "主角第一次有效反击必须改变资源、关系或信息状态，不能只获得口头胜利。" \
  --rule "主角第一次有效反击必须改变资源、关系或信息状态，不能只获得口头胜利。" \
  --source-name codex-conversation.md \
  --title "首次有效反击" \
  --rationale "可观察的状态变化才能让反击进入后续因果。" \
  --category "分集与卡点" \
  --stage episode \
  --genre "女频复仇" \
  --production-mode all \
  --priority preferred \
  --exceptions "经确认的前期压抑型结构" \
  --positive-example "女主公开账本后夺回项目表决权。" \
  --negative-example "女主只把反派骂走，局势没有变化。" \
  --status active
```

当用户粘贴的原文还包含适用范围、课程解释等内容时，`--text` 保留完整原文，`--rule` 只放提炼后的单条原子规则；二者不要互相替代。

需要先人工复核时省略覆盖字段，并保持默认 `draft`：

```bash
python3 mm-write-short-drama/scripts/ingest_knowledge.py \
  --kb ./knowledge-base \
  --text "这里粘贴课程、文章或自己的编剧总结" \
  --source-name lesson-12.md
```

### 批量录入多期资料

先把 `.md` / `.txt` 放入 `knowledge-base/inbox/`，再运行：

```bash
python3 mm-write-short-drama/scripts/ingest_knowledge.py \
  --kb ./knowledge-base \
  --all-inbox
```

脚本不会移动、改名或删除 Inbox 原文件。原文副本进入 `sources/`，重复规则只记日志，疑似冲突变为 `pending-conflict`。

### 检索当前阶段知识

```bash
python3 mm-write-short-drama/scripts/search_knowledge.py \
  "女主第一次反击和本集结尾卡点" \
  --kb ./knowledge-base \
  --stage episode \
  --genre "女频复仇" \
  --production-mode live-action \
  --limit 8 \
  --format context
```

默认只返回 `active`。当前项目明确要求和锁定事实始终优先；`pending-conflict` 不会被调用。

v1.3.0 支持在语义诊断后用 `--capability <原能力ID>` 精确补查；卡片保留 `source_note / source_url / source_verification` 等来源字段。五书24项摘要、能力 ID 和核验边界见 [当前设计](current-design.md#五书方法与来源)。同能力个人已启用卡优先，当前随包摘要兜底；三张旧公开卡保留兼容。能力接口不表示仓库附带对应书籍全文或已审核私人卡。

### 校验知识库

```bash
python3 mm-write-short-drama/scripts/validate_knowledge.py \
  --kb ./knowledge-base \
  --fix-index
```

### 裁决冲突

```bash
python3 mm-write-short-drama/scripts/ingest_knowledge.py \
  --kb ./knowledge-base \
  --resolve KBC-XXXXXXXXXXXX \
  --decision keep-existing
```

也可选择 `activate-new`；若选择 `keep-both`，必须用 `--note` 写清两条规则已经分离的适用范围。

## 正式项目工作流

脚本负责证据、覆盖、版本、状态和文件检查，语义与创作判断由实际读稿的编剧/审核者完成。命令帮助以当前源码 `--help` 为准。可以先建空骨架，但首个用户选择仍是AI/真人。`init --mode` 只决定骨架，不能当作用户已选来源；用 `set-specs --source-mode` 记录来源回执后，程序按来源补齐空骨架，不覆盖已有正文。切换明确来源时，旧 `source-evidence.json` 按原字节归档至 `.drama/source-route-history/<sha>.json`，新路由证据重新登记，防止旧证据冒充新来源。

```bash
SKILL_DIR=./mm-write-short-drama
PROJECT=./projects/example
python3 "$SKILL_DIR/scripts/init_project.py" "$PROJECT" --mode original
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" status
```

来源回执分别用 `--source-mode original`、`--source-mode adaptation`、`--source-mode market_research`；骨架对应 `--mode original|adaptation|market-research`。旧 `--mode source-remix` 保留原素材再创作含义，不能自动改标为近期检索。`--through brief|story-bible|full` 仅决定创建骨架的范围，文件存在不等于内容完成。

缺规格的骨架保持 `awaiting_production_specs`，`status` 依次显示等待制作方式、创作来源、单集时长或期望集数。用以下命令逐步转录真实选择（所有引号示例须换成用户真实原话与消息定位）：

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

来源选定后了解题材与其他普通需求，再记录时长和期望集数；题材等普通需求可先标待定。AI用 `--production-mode ai_drama`；`--source-mode` 支持 `original|adaptation|market_research`，`source_remix` 仅兼容旧项目；范围时长用 `--duration-range 50-60`。新增来源/时长/集数参数必须配真实回执；旧制作方式/骨架路线/总数参数不自动成为已选。四项未齐不能运行 treatment/outline 审读或进入分集、正文。

用户已明确四项选择后，可以一次初始化（例中的自己编写来源也已明确）：

```bash
python3 "$SKILL_DIR/scripts/init_project.py" ./projects/complete-example --mode original \
  --production-mode live_action --source-mode original --duration-seconds 90 --episode-count '40-60' \
  --specs-user-quote '用户实际说全四项规格的原话' --specs-message-ref '真实消息定位'
```

期望数保存在 `.drama/production-specs.json`；实际总数和理由另存 `.drama/episode-plan.json`，`state.totalEpisodes` 镜像实际数。规格齐全、写好来源证据和故事底稿后：

```bash
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" status
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" review-pack --stage treatment
```

命令返回本次 `READ-...` session ID及按顺序的正文分块。先实际读分块，保存首读笔记，再打开来源和大纲。以下使用返回的真实ID替换 `READ-...`：

```bash
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" report-template --session READ-... --output review-template.json
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" first-read --session READ-... --report first-read.json
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" reveal-context --session READ-...
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" record-review --session READ-... --report reviewed.json
```

模板包含 `firstRead` 与 `secondPass` 两个对象，需分别取出，在实际阅读后填写为上面的两个文件。空模板、`read:true` 或计分不能代替实读。每个检查域和问题都需可回指的原文证据；返回阻断问题时按根因返修，用新正文创建新会话复检。

底稿通过后补大纲和圣经，按完整故事记录实际规划数（58只是命令示例）：

```bash
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" set-plan \
  --total-episodes 58 --reason '当前故事各阶段的实际规划理由'
```

再运行 `review-pack --stage outline`，重复两遍审读。底稿绑定规格，大纲及后续审读另绑定实际规划；定实际数不无故使已审底稿失效。用户真实确认该版之后才执行：

```bash
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" confirm-outline \
  --decision confirm --quote '用户实际确认原话' --message-ref '真实对话定位' --scope '全剧大纲及本次交付范围'
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" check-writing
```

不能把示例中的引号内容当作用户授权。用户要求修改时用 `--decision revise` 记录实际意见，再改稿、重审、重新确认。`status` 在重启时发现内容变化会持久化失效状态。

正文阶段先用 `build_context_pack.py "$PROJECT" --episodes 1-5` 装配上下文，再用 `review-pack --stage batch --episodes 1-5` 批审。逐集状态仍由 `update_episode_state.py` 维护，但批准须有当前有效批审证据和实际文件，调用者不能自行声明问题数替代审核。上游影响分析仍用 `impact_analysis.py`；已有修改授权可按其范围执行，不能擅改锁定内容。

### 润色与正式 Word

先保存前后稿，按需局部编辑或原样通过，用 `polish_guard.py inspect|record|check` 留下当前hash的最终语义复核记录。程序是保守差异检查，金额、责任人、日期、否定、条件与承诺仍需逐处读。外部Humanizer的旧token检查单独通过不构成语义通过。

Word的“类型/短剧类型”填写题材，制作方式单独记录。正式Word的全剧集数按 `state.totalEpisodes` 实际规划填写，不用期望数或范围冒填。首集之前按顺序包含：剧本名、来源、类型/短剧类型、集数（全剧与本稿范围）、剧名寓意、热门元素、创作理由、故事梗概、主要角色。由已确认材料生成当前项目内容，不能套用样剧人物、空标题或虚构署名。分批稿写清本批收束与未来回收归属。

```bash
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" review-pack \
  --stage final --episodes 1-5 --front-matter "$PROJECT/front-matter.md"
```

完成最终两遍通读、当前问题清零和事实复核后检查并暂存：

```bash
python3 "$SKILL_DIR/scripts/workflow.py" "$PROJECT" check-release \
  --episodes 1-5 --front-matter "$PROJECT/front-matter.md"
python3 "$SKILL_DIR/scripts/export_screenplay_docx.py" \
  "$PROJECT/episodes/EP001.md" "$PROJECT/episodes/EP002.md" "$PROJECT/episodes/EP003.md" \
  "$PROJECT/episodes/EP004.md" "$PROJECT/episodes/EP005.md" \
  --project-dir "$PROJECT" --project-title 项目名 --front-matter "$PROJECT/front-matter.md" \
  --output "$PROJECT/deliverables/项目名_第01-05集.docx"
```

导出输入目录必须只含该批要交付的集；也可显式列出本批文件。命令先输出 `.drama/staging/` 中待验收的Word和清单，尚未写正式交付文件。用同一bundled Python执行实际渲染包装器，指定真实的文档渲染脚本；输出目录必须是新的，不能给旧图片补认证：

```bash
python3 "$SKILL_DIR/scripts/render_screenplay.py" /absolute/project/.drama/staging/returned-file.docx \
  --renderer /实际bundled路径/documents/render_docx.py \
  --output-dir /absolute/project/work/word-render-新版本
```

包装器实际调用渲染器，输出PDF、全部页图和 `render-manifest.json`。逐页打开图片检查，在视觉QA中记录准确docx hash、审核者、全部页图hash及观察；`QA.renderManifest` 必须指向本次包装器实际生成的 `render-manifest.json`，`renderDirectory` 指向其目录。发布时重新读取PDF真实页数、核对每页尺寸与摘要，并检查manifest绑定的Word和渲染器；1×1占位图、缺页或另一份Word的旧渲染不能用QA自报hash放行。然后执行：

```bash
python3 "$SKILL_DIR/scripts/export_screenplay_docx.py" \
  --publish /absolute/project/.drama/staging/returned-file.docx --visual-qa /absolute/project/visual-qa.json
```

正式文件不能覆盖；重试使用新版本路径。正文、大纲、前置内容或待交付Word变化后，相关审核/确认/实物验收失效。版式预览必须显式 `--preview`，页面标识预览，不计正式状态。详见 [Word规则](../mm-write-short-drama/references/word-delivery.md)。

默认版式保留宋体、13磅总标题、10.5磅正文、1.4倍行距、黄色标题行、蓝色台词和真实PAGE/NUMPAGES。各集连续流排，一批全部集数一个Word；不在Word里重新改对白。

### 其他工具

- `index_source.py`：索引原著，记录文件hash与章节/行号；
- `validate_project.py`、`validate_state.py`：检查文件、字段、依赖和状态；
- `screenplay_stats.py`：检查场数、对白与粗估时长，不能替代朗读；
- `import_book_capabilities.py`：隔离导入、核查后启用、显式迁移旧六卡；
- `search_knowledge.py --format context`：查询落笔需要的完整执行字段；
- `validate_knowledge.py`：核来源hash、能力版本与索引。

### 润色设置与记录

默认 `local`，只改已定位的表达问题；`off` 使用相同前后稿并记录实际事实复核；`full` 仅在项目明确选择后使用。独立主笔稿把具体问题送回同一主笔，不在汇总时再合写。`polish_guard.py inspect` 生成差异和保守风险提示，`record` 接受真实逐差异语义复核，`check` 检查当前稿件与已审哈希。已使用随包或外部 Humanizer 时记录唯一实际调用链；其旧 token 校验不能替代语义复核。[完整字段与命令](../mm-write-short-drama/references/humanizer-adapter.md)

### 仅预览版式

```bash
python3 "$SKILL_DIR/scripts/export_screenplay_docx.py" "$PROJECT/episodes/EP001.md" \
  --project-title 格式预览 --output /tmp/screenplay-preview.docx --preview
```

预览明确标识尚未通过正式交付，不写正式状态，前置内容可省略。正式导出要求 `--project-dir`、`--front-matter`、当前有效的确认和审读，先暂存，实际渲染和逐页检查后才 `--publish`。

### 给原著建立稳定索引

```bash
python3 "$SKILL_DIR/scripts/index_source.py" ./source/novel.md \
  -o ./projects/my-adaptation/01-source-index.md
```

支持一个或多个 `.md` / `.txt` 文件或目录。章节索引包含稳定 Source ID、行号、字符数和内容摘要哈希，便于改编事实引用证据位置。

### 构建一批剧本的最小上下文包

```bash
python3 "$SKILL_DIR/scripts/build_context_pack.py" ./projects/my-drama \
  --episodes 6-10
```

默认输出到 `context-packs/EP006-EP010-context.md`。上下文包是源文件快照，不会成为新的事实源；正式写作前仍需核对关键账本。

### 校验项目结构

```bash
python3 "$SKILL_DIR/scripts/validate_project.py" ./projects/my-drama --mode original
python3 "$SKILL_DIR/scripts/validate_project.py" ./projects/my-adaptation --mode adaptation --json
python3 "$SKILL_DIR/scripts/validate_project.py" ./projects/my-gate-a --mode original --stage gate-a
```

脚本检查必需文件、CSV 字段、剧本标题/控制信息/连续性更新、标准场景头和分集矩阵映射。错误返回非零退出码，警告不会阻断。

### 统计剧本

```bash
python3 "$SKILL_DIR/scripts/screenplay_stats.py" ./projects/my-drama/episodes
python3 "$SKILL_DIR/scripts/screenplay_stats.py" ./projects/my-drama/episodes --json
```

统计场次、对白行/字数、动作字数、说话角色和粗略时长。时长只是异常检测信号，不替代朗读、表演节奏和剪辑判断。

所有脚本的完整参数均可用 `--help` 查看。

### 个人知识库脚本

- `ingest_knowledge.py`：保留原文、提炼候选原子规则、分类、查重、冲突冻结、用户裁决和重建索引；
- `search_knowledge.py`：按任务、阶段、题材、制作模式和状态检索；
- `validate_knowledge.py`：检查卡片字段、来源哈希、冲突状态和索引；
- `knowledge_lib.py`：三套命令共享的标准库实现。

## 开发与验证

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py ./mm-write-short-drama
python3 -m py_compile ./mm-write-short-drama/scripts/*.py
python3 -m unittest discover -s tests -v
python3 ./mm-write-short-drama/evals/test_p0.py
python3 ./tests/validate_seeded_knowledge.py
python3 ./mm-write-short-drama/scripts/validate_knowledge.py --kb ./mm-write-short-drama/knowledge-base
```

建议用 [测试提示集](test-prompts.md) 做触发、原创、改编、连续性陷阱、去 AI 味和技巧冲突回归测试。
