# 命令行使用手册

以下命令从仓库根目录运行。想直接在 Codex 对话里立项、续写或审稿，可从 [项目首页](../README.md) 选择相应示例。

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

v1.2.0 支持在语义诊断后用 `--capability <原能力ID>` 精确补查；卡片保留 `source_note / source_url / source_verification` 等来源字段。五项能力入口、ID 和核验边界见 [当前设计](current-design.md#五项写作能力与知识来源)。能力接口不表示仓库附带对应书籍全文或已审核私人卡。

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

## 项目与 Word 导出命令

这些脚本负责可重复的初始化、索引、状态迁移、依赖分析、装配、校验、统计和 Word 导出；创作质量仍由工作流审核。

```bash
SKILL_DIR=./mm-write-short-drama
```

### 初始化项目

```bash
python3 "$SKILL_DIR/scripts/init_project.py" ./projects/my-drama --mode original
python3 "$SKILL_DIR/scripts/init_project.py" ./projects/my-adaptation --mode adaptation
python3 "$SKILL_DIR/scripts/init_project.py" ./projects/my-gate-a --mode original --through story-bible
python3 "$SKILL_DIR/scripts/init_project.py" ./projects/my-remix --mode source-remix \
  --production-mode live_action --orientation vertical --total-episodes 6
```

`--through brief` 只创建启动阶段文件；`--through story-bible` 创建到审核门 A；默认 `full` 创建完整骨架。为保护已有项目，目标目录非空时脚本会拒绝覆盖。

### 状态恢复与上游影响分析

```bash
python3 "$SKILL_DIR/scripts/validate_state.py" ./projects/my-drama --json
python3 "$SKILL_DIR/scripts/impact_analysis.py" ./projects/my-drama \
  --changed 04-story-bible.md --json
```

影响分析默认只读。用户批准具体变更后才加 `--apply --approved-by ... --reason ...` 标记依赖失效；脚本不会自动重写正文。逐集通过 `update_episode_state.py` 记录 `planned → draft → in_review → revision/in_review → approved`，批准前要求阻断问题清零并记录上游 revision。完整命令和校验边界见 [当前设计](current-design.md#单集状态与版本依赖)。

### 合并导出 Word

```bash
python3 "$SKILL_DIR/scripts/export_screenplay_docx.py" \
  ./projects/my-drama/episodes/EP001.md ./projects/my-drama/episodes/EP002.md \
  --output ./projects/my-drama/deliverables/项目名_第01-02集.docx \
  --project-title 项目名
```

默认采用 `assets/screenplay-base-template.docx`：宋体、13 磅总标题、10.5 磅正文、1.4 倍行距、标题行黄色高亮、蓝色台词及真实页码字段。导出先清除中性占位，仅写入当前项目内容，并隐藏控制信息和连续性维护区。可选 `--front-matter ./projects/my-drama/front-matter.md` 只输出用户明确提供且已审核的当前项目前置内容；未提供就不输出。一个批次一个 Word，各集不强制另起一页。详见 [Word 交付规则](../mm-write-short-drama/references/word-delivery.md)。

真实剧本须先完成内容审核、外部 Humanizer 编辑与记录，再导出并渲染逐页检查。导出脚本本身不会证明这些门已通过。

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
```

建议用 [测试提示集](test-prompts.md) 做触发、原创、改编、连续性陷阱、去 AI 味和技巧冲突回归测试。
