# Data Format Specification

This document describes the two JSON files required by `build_report.py`.

---

## 1. `chat.json` — Raw chat records

A JSON array of message objects. Each object must have at minimum:

```json
[
  {
    "sender":    "张三",
    "content":   "今天天气真好！",
    "type":      "text",
    "timestamp": 1704067200
  },
  {
    "sender":    "李四",
    "content":   "",
    "type":      "image",
    "timestamp": 1704067260
  }
]
```

### Required fields

| Field       | Type             | Description                                             |
|-------------|------------------|---------------------------------------------------------|
| `sender`    | string           | Display name of the message sender                      |
| `content`   | string           | Message text (empty string for non-text types)          |
| `type`      | string           | Message type — see table below                          |
| `timestamp` | integer (Unix s) | Unix timestamp in **seconds**                           |

### Supported `type` values

| Value      | Label  |
|------------|--------|
| `text`     | 文本   |
| `image`    | 图片   |
| `sticker`  | 表情   |
| `link`     | 链接   |
| `file`     | 文件   |
| `video`    | 视频   |
| `voice`    | 语音   |
| `call`     | 通话   |
| `reply`    | 回复   |
| `system`   | 系统   |
| `location` | 位置   |

### Optional field

| Field       | Type   | Description                               |
|-------------|--------|-------------------------------------------|
| `xiehouyu`  | string | A custom closing quote shown on the report (歇后语 / easter egg text) |

The `xiehouyu` field can also be a top-level key in a wrapper object:

```json
{
  "messages": [...],
  "xiehouyu": "\"有些人消失在群里——但从未真正离开过截图。\""
}
```

If omitted, a built-in default phrase is used.

---

## 2. `topN.json` — Chart extracts

Produced by `src/extract_topn.py`. Contains the top-N ranked entries for each chart extracted from a Plotly HTML report.

```json
{
  "group":  "我的群组",
  "source": "report.html",
  "charts": [
    {
      "chart": "总发言排行",
      "topn": [
        {"rank": 1, "name": "张三", "value": 1280},
        {"rank": 2, "name": "李四", "value": 974},
        {"rank": 3, "name": "王五", "value": 831},
        {"rank": 4, "name": "赵六", "value": 650},
        {"rank": 5, "name": "钱七", "value": 512}
      ]
    },
    {
      "chart": "后起之秀",
      "topn": [
        {"rank": 1, "name": "新人甲", "value_y": 3.2, "value_x": 45},
        {"rank": 2, "name": "新人乙", "value_y": 2.8, "value_x": 62}
      ]
    }
  ]
}
```

### `charts[].topn` item shapes

**Bar / pie charts** (most charts):
```json
{"rank": 1, "name": "张三", "value": 1280}
```

**Scatter charts** (后起之秀):
```json
{"rank": 1, "name": "新人甲", "value_y": 3.2, "value_x": 45}
```
`value_y` = daily average messages; `value_x` = days since first message.

### Chart title keywords used by `build_report.py`

The report generator matches chart titles by keyword substring. The expected chart names are:

| Keyword (substring) | Leaderboard category |
|---------------------|---------------------|
| `总发言排行`         | 总发言王             |
| `发图`              | 发图达人             |
| `发链接`            | 链接分享王           |
| `夜猫子`            | 夜猫子               |
| `早起鸟`            | 早起鸟               |
| `最激烈`            | 最激烈时段           |

---

## Generating `topN.json` from an existing Plotly HTML report

```bash
# Default: top 5
python src/extract_topn.py path/to/report.html

# Custom N
python src/extract_topn.py path/to/report.html --n 10

# Batch (parallel)
python src/extract_topn.py group1/report.html group2/report.html --n 5
```

Output is written as `top5.json` (or `top{n}.json`) in the same directory as the HTML file.
