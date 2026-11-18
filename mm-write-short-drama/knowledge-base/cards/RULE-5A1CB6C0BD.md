# 按紧张与释放重排分集节奏

<!-- knowledge-card:start -->
```json
{
  "id": "RULE-5A1CB6C0BD",
  "title": "按紧张与释放重排分集节奏",
  "rule": "节奏拖沓时，分别检查场次长短、内部活动强度和主线压力，再决定删减、合并或调换。",
  "rationale": "场景长度、内部活动强度和紧张释放的排列共同影响观看节奏。",
  "category": "分集",
  "stage": [
    "structure",
    "episode",
    "review"
  ],
  "genre": [
    "all"
  ],
  "production_mode": [
    "all"
  ],
  "priority": "optional",
  "exceptions": [
    "电影平均场长与银幕页数只描述原书语境。短剧用实际集长和试读时长估算",
    "安静场也可承担高压力。"
  ],
  "positive_example": "连续三场追问证人合成一场，再留一场主角独自看旧录音的低活动场，让亲情代价进入下一次选择。",
  "negative_example": "把所有沉默都删掉，每场都以吼叫结束，主角作决定所需的犹疑与信息也消失了。",
  "source": {
    "source_id": "SRC-20261118-AF05B8CF2C68",
    "stored_path": "knowledge-base/sources/SRC-20261118-AF05B8CF2C68--story-13-composition-rhythm.md",
    "original_name": "story-13-composition-rhythm.md",
    "sha256": "af05b8cf2c6872aea8ba02c20e40fa3eb1e0752d369118d0278b65034f1046cf",
    "captured_at": "2026-11-18T15:36:51+08:00"
  },
  "source_note": "罗伯特·麦基著，周铁东译，天津人民出版社，2014年9月第1版，ISBN 9787201088334，第12章《布局谋篇》／统一性和多样性；进度；节奏和速度；过渡原理，index_split_031.html P0001—P0026、P0069—P0080。短剧操作字段、范例及验收方式为本项目适配。电子文件包含推广字样及少量讹误，位置以文件哈希为准。",
  "source_url": "https://github.com/pipivv/gushi-skill/blob/8b68e5d0474f0a1dee55855ccb471eb35462bda1/故事-麦基.epub",
  "capability_id": "cap.mckee-story-short-drama.composition-rhythm",
  "triggers": "用户要按紧张与释放重排分集节奏，或在分集阶段提出相关问题时使用。输入为当前项目的设定、场次或大纲，按E段确认具体字段。 相邻任务可按末尾的关联卡继续阅读，优先使用本次任务直接需要的规则。",
  "diagnosis": "先读取本次项目设定、当前场次或大纲，按本卡规则检查具体缺口，结合例外判断是否适用。规则为节奏拖沓时，分别检查场次长短、内部活动强度和主线压力，再决定删减、合并或调换。",
  "action": "1. 输入分集或场次表及项目目标时长。 2. 逐场标注估计时长、行动强度、价值变化与主线用途，标明时长是估计还是实测。 3. 检查连续场次是否在相同地点重复同种交流，或一直保持同一强度，寻找合并及紧张释放的位置。 4. 用相邻场次的变化或相通元素设计过渡，保持因果与时间连戏。 5. 交付调整前后镜序和理由，核验新增速度没有删掉决定所需的信息。 完成时须交付上述表格或修订文本、具体修改理由、原章节定位和未确定事实。重要情节的改变应记录影响范围。输入不足时先列缺失字段，再完成已有信息支持的部分。",
  "output_contract": "按动作段指定的表格或修订场次交付，包含原始问题、所选调整、改变后的行动或事实、来源定位与待定项。",
  "self_check": "核对任务所需字段已交付、变化有具体行为或证据、前后因果成立、人物知情与项目锁定事实一致、每项新增情节已标记，最后复查本卡B段例外。",
  "adaptation": "步骤、表格和演练为本项目适配；按目标集数、集长、制作形态和锁定事实决定改写范围。原书章节与电子段号用于回查，观众效果需要实际反馈。",
  "source_verification": "中文EPUB的CIP、版权页、译者与ISBN已核对；19章索引扫描及入选方法段回读，来源定位和必要条件已复核；第三方文件、纸本页码、全文逐字校勘及部分图像/史实仍保留缺口。",
  "capability_revision": 1,
  "original_source_sha256": "8bf058b9180a4b945bb2f5fc8505a1304367ff551b191241d7ccf68553500f60",
  "source_commit": "6e99009572a64f99d60134405fbf1cf200b0dfe4",
  "status": "active",
  "version": 1,
  "created_at": "2026-11-18T15:36:51+08:00",
  "updated_at": "2026-11-18T15:36:51+08:00",
  "import_sha256": "af05b8cf2c6872aea8ba02c20e40fa3eb1e0752d369118d0278b65034f1046cf",
  "upstream_path": "knowledge-inbox/story-13-composition-rhythm.md",
  "source_locator": "罗伯特·麦基著，周铁东译，天津人民出版社，2014年9月第1版，ISBN 9787201088334，第12章《布局谋篇》／统一性和多样性；进度；节奏和速度；过渡原理，index_split_031.html P0001—P0026、P0069—P0080。短剧操作字段、范例及验收方式为本项目适配。电子文件包含推广字样及少量讹误，位置以文件哈希为准。",
  "provenance_layers": {
    "book_principle": "source_note and source_verification identify available evidence",
    "short_drama_operations": "action, output_contract, self_check, adaptation are project adaptation",
    "examples": "positive_example and negative_example are upstream original exercises"
  },
  "original_edition": {
    "title": "故事：材质、结构、风格和银幕剧作的原理",
    "author": "罗伯特·麦基",
    "translator": "周铁东",
    "publisher": "天津人民出版社",
    "edition": "2014年9月第1版、第1次印刷",
    "isbn": "9787201088334",
    "version_id": "tj-2014-09-8bf058b9180a"
  },
  "story_number": 13,
  "activation_review": {
    "review_note": "逐卡核对固定提交导入稿的规则、阶段、例外、执行字段及来源定位，19项版本和源哈希与上游清单一致。上游原书核验声明保留为上游记录；本轮未重新读取原书全文，纸本页码仍待核。",
    "reviewed_at": "2026-11-18T15:36:51+08:00",
    "input_sha256": "af05b8cf2c6872aea8ba02c20e40fa3eb1e0752d369118d0278b65034f1046cf"
  },
  "original_source_commit": "8b68e5d0474f0a1dee55855ccb471eb35462bda1"
}
```
<!-- knowledge-card:end -->

## 人工备注

- 待验证问题：
- 适用边界：
