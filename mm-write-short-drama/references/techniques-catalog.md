# 知识卡规范

每张知识卡位于根目录 `knowledge-base/cards/<id>.md`，使用 Markdown 包裹机器可读 JSON。字段必须包括：

| 字段 | 约束 |
|---|---|
| `id` | 按规则正文哈希生成的稳定 ID，不随标题改变 |
| `title` | 简短人类可读标题 |
| `rule` | 单一、可执行、可验证的原子规则 |
| `rationale` | 规则有效的原因 |
| `category` | 开场、人物、结构、分集、场景、对白、改编、制作、审核等 |
| `stage` | `planning/structure/episode/scene/dialogue/review/adaptation/all` 数组 |
| `genre` | 适用题材数组，通用用 `all` |
| `production_mode` | `live-action/ai/hybrid/unspecified/all` 数组 |
| `priority` | `hard/preferred/optional/experimental` |
| `exceptions` | 不适用条件数组 |
| `positive_example` | 能说明规则的正例 |
| `negative_example` | 能说明失败方式的反例 |
| `source` | 原始资料 ID、路径、文件名、SHA-256 和保存时间 |
| `status` | `draft/active/pending-conflict/duplicate/rejected/deprecated/archived` |
| `version` | 正整数；显式状态/内容变化时递增 |

`active` 才可默认检索。稳定 ID 和旧版本不得被新规则静默覆盖；状态变化前保存归档快照。详细流程读取 [knowledge-base.md](knowledge-base.md)。
