# 正式 Word 导出与实物验收

每批一份 Word，包含本批全部集数，按集号连续流排；只有明确要求整季合订才合并整季。文件名为“项目名_第起始集-结束集.docx”，单集为“项目名_第NN集.docx”。格式来自 `assets/screenplay-base-template.docx`；样剧只提供版式，不提供本项目的任何剧情、人物或署名。现有宋体、黄色集场人物行、蓝色台词和动态 `PAGE / NUMPAGES` 保持；场次头规范为“1-1 日 内 地点”。

## 正式件的九个前置模块

首页剧名之下、首集之前按顺序列出：剧本名、来源、类型或短剧类型、集数、剧名寓意、热门元素、创作理由、故事梗概、主要角色。已按本地原模板核实：来源与类型是两个独立段落，字段原名为“类型”；前六项沿用同行标签与内容，后三项为独立标题和正文。“短剧类型”保留为旧输入别名；此处“类型”填写题材，制作方式与创作来源各自独立，不用AI/真人替代题材。使用 [前置模块模板](../assets/front-matter-template.md) 的栏目，由已确认材料生成当前项目内容并审读，禁止空标题、占位、虚构署名和串入样剧。原参考有额外正文前模块时一并保留并审查。

“集数”按大纲实际规划总数 `state.totalEpisodes` 同时写全剧总数和本稿范围，例如“全剧共50集，本稿为第1—30集正式剧本”。不得用 `.drama/production-specs.json` 的用户期望具体数或范围冒填实际总数。脚本核对总数、范围、顺序、重复和断号；梗概落到本批实际收束点，全剧规划另标。角色每人一段，写身份、关系、目标、局限、典型选择及变化。热度主张需日期与来源；无热度证据可只写本稿实际看点。事实准确、内容完整和人物简介质量由最终阅读负责，不能为空校验代替。

## 暂存 再验收 再发布

正式 CLI 默认要求项目、已审前置信息、当前大纲人工确认、批审及最终正文覆盖与问题记录。`validate_release` 从记录和当前内容哈希计算，调用者传零无效。

```bash
python3 "$SKILL_DIR/scripts/export_screenplay_docx.py" project/episodes/EP001.md \
  project/episodes/EP002.md --project-dir project \
  --front-matter project/front-matter.md --project-title 项目名 \
  --output project/deliverables/项目名_第01-02集.docx
```

成功只生成 `project/.drama/staging/` 下临时 Word 和 manifest，返回 `awaiting_visual_qa`。脚本重新打开 Word，将全部可见段落与已审来源逐段比较，保留来源与导出摘要；不重新润色正文。指定的正式路径此时不存在。

用 documents skill 的 bundled runtime 执行随包 `render_screenplay.py`，指定实际 bundled `render_docx.py`。包装器在一个全新目录实际运行渲染，强制输出 PDF 与全部页图，并写入 `render-manifest.json`；它没有给既有图片目录补认证的入口。

```bash
python3 "$SKILL_DIR/scripts/render_screenplay.py" project/.drama/staging/本次暂存名.docx \
  --renderer /实际bundled路径/documents/render_docx.py \
  --output-dir project/work/word-render-新版本
```

manifest 绑定输入 Word、实际渲染器及 PDF 的 SHA256、实际执行命令、PDF 真实页数与页面尺寸、全部 PNG 的摘要和尺寸。发布时重读 PDF，核对完整页图集合；1×1 占位图、缺页、不同 Word 的旧渲染或改动后的页图均不能通过。PDF 校验优先用 PyMuPDF；当前 bundled 环境缺少它时使用同环境的 pypdf，图像尺寸用 Pillow。打开每一页，检查中文、完整分页、空白、裁切、重叠、场次与对白、高亮和页码。macOS 宋体缺字时，仅为渲染命令临时将 Fontconfig 的宋体映射为 `Songti SC`；最终 DOCX 仍声明宋体。修改后重新导出、渲染、检查，旧 QA 不能复用。

实际检查后写 QA JSON：

```json
{
  "docxHash": "本次暂存Word的SHA256",
  "reviewer": "实际检查者",
  "passed": true,
  "notes": "每页实际看到的结果及必要的版式取舍",
  "renderDirectory": "/absolute/path/to/rendered-pages",
  "renderManifest": "/absolute/path/to/rendered-pages/render-manifest.json",
  "pages": [
    {"path": "/absolute/path/to/rendered-pages/page-1.png", "sha256": "图像SHA256", "inspected": true}
  ]
}
```

`pages` 必须覆盖目录内所有连续编号的 `page-N.png`。这是实际人工或模型视觉检查的记录，不是自动证明排版无误。不得生成虚假的检查记录。

```bash
python3 "$SKILL_DIR/scripts/export_screenplay_docx.py" \
  --publish project/.drama/staging/本次暂存名.docx \
  --visual-qa project/work/visual-qa.json
```

发布前重新核对正文、前置信息、审核门、来自实际渲染的manifest及其PDF/完整页图哈希与尺寸，成功后才写入正式交付目录并附 `.delivery.json`。正文或大纲变化后旧审稿失效；暂存后改动须重新审查并暂存。既有正式件不可覆盖，重试选新版本文件名。

## 版式预览

```bash
python3 "$SKILL_DIR/scripts/export_screenplay_docx.py" examples/EP001.md \
  --output /tmp/layout-preview.docx --project-title 格式预览 --preview
```

预览显式出现“版式预览 尚未通过正式交付验收”，不占批准或正式交付状态，前置信息可选。旧包装直接调用 `build_docx` 时默认生成带标记的预览；正式构建必须带项目、前置材料并写暂存目录，不能绕过正式门。纯模板预览无需剧情润色，但交付预览实物仍须看渲染；正式正文的最终语义复核见 [Humanizer 适配](humanizer-adapter.md)。

只读验证现有同哈希文件可调用 `render_screenplay.verify_render_manifest(docx_path, manifest_path, render_directory=None)`，返回错误列表；它不修改 Word、图片、manifest 或发布状态。渲染记录证明工具执行与产物版本关系，实际排版结论仍须读每页图，不能由metadata代替。

## 准备 Word 导出环境

优先使用 Codex 工作区提供的 Python、文档依赖和真实 `render_docx.py`。导出需要 `python-docx`，渲染证据校验需要 Pillow 及 PyMuPDF 或 pypdf；渲染器本身的依赖按其实际文档环境准备。没有可用工作区依赖时，可为项目创建独立环境，安装本 Skill 的随附清单：

```bash
python3 -m venv "$PROJECT/.drama/word-venv"
"$PROJECT/.drama/word-venv/bin/python" -m pip install -r "$SKILL_DIR/scripts/requirements-word.txt"
"$PROJECT/.drama/word-venv/bin/python" -c "import docx, PIL, pypdf"
```

Windows 解释器路径为 `.drama/word-venv/Scripts/python.exe`。首次安装需要可达包源，后续用同一个已验证解释器运行导出和校验。依赖清单不安装文档渲染器；缺少实际渲染方式时只能保留暂存稿或标明预览，待渲染和逐页实物检查完成后才发布正式件。
