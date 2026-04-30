# 群聊信息分析 · WeChat Group Chat Analytics

将微信群聊记录转化为精美的可交互 HTML 数据报告。

> Apple 设计风格 · 拖拽磁贴排行榜 · 人物画像 · 词频分析 · 滚动动画

---

## 效果预览

| 模块 | 说明 |
|------|------|
| 🏆 拖拽排行榜 | Top 5 磁贴，拖动翻转揭晓姓名，全部翻开触发彩蛋 |
| 📊 综合榜单 | 20 人可排序表格，前 3 名粗体，鼠标悬停显示占比 |
| 👤 人物画像 | 消失的人 / 少言寡语 / 后起之秀 / 时间线 / 词频 / 个人词频 |
| 🔢 动态计数 | 关键数字滚动计数动画（IntersectionObserver 触发）|
| 🌟 滚动揭示 | 卡片随滚动淡入 / 放大出现 |

---

## 完整流程

数据来源是微信本地数据库，通过 [wechat-cli](https://github.com/freestylefly/wechat-cli) 导出，再经过本工具链处理成 HTML 报告。

```
wechat-cli export  →  聊天记录.md
        │
        ├── analyze_chat.py  →  Plotly report.html
        │                              │
        │                    extract_topn.py  →  top5.json ──┐
        │                                                     │
        └── md_to_json.py  →  chat.json ──────────────────────┤
                                                              │
                                                    build_report.py
                                                              │
                                                      最终 report.html
```

**📖 详细步骤请看 → [docs/wechat-cli-guide.md](docs/wechat-cli-guide.md)**（含超过 10 万条消息的大群处理方案）

---

## 快速开始

### 1. 安装依赖

```bash
# wechat-cli（需要 Node.js）
npm install -g @canghe_ai/wechat-cli

# Python 依赖
pip install -r requirements.txt
pip install pandas plotly emoji   # analyze_chat.py 额外需要
```

### 2. 导出聊天记录

```bash
# 首次初始化（微信需保持运行）
wechat-cli init         # macOS/Linux 加 sudo

# 导出为 Markdown
wechat-cli export "群聊名称" --format markdown --limit 9999999 --output 群聊名称聊天记录.md

# 超过 10 万条？用 --offset 分批追加到同一文件，无需合并：
wechat-cli export "大群" --format markdown --limit 99999 --offset 0   --output 大群.md
wechat-cli export "大群" --format markdown --limit 99999 --offset 99999 >> 大群.md
# 详见 docs/wechat-cli-guide.md
```

### 3. 转为 JSON

```bash
python md_to_json.py 群聊名称聊天记录.md   # → 群聊名称聊天记录.json
```

### 4. 提取图表 Top-N 数据

```bash
python src/extract_topn.py path/to/report.html   # → top5.json
```

详见 [`examples/data_format.md`](examples/data_format.md)。

### 5. 生成 HTML 报告

```bash
# Apple 主题（默认）
python src/build_report.py top5.json chat.json -o report.html

# 暖色主题
python src/build_report.py top5.json chat.json -o report.html --theme warm
```

用浏览器打开生成的 `report.html` 即可。

---

## 文件结构

```
wechat-group-analytics/
├── src/
│   ├── build_report.py   # 报告生成器（主程序）
│   ├── extract_topn.py   # 从 Plotly HTML 提取 Top-N 数据
│   └── chat_utils.py     # 分词、停用词、消息类型标签
├── examples/
│   └── data_format.md    # 输入 JSON 格式说明
├── requirements.txt
└── README.md
```

---

## 主题

| 主题 | 参数 | 风格 |
|------|------|------|
| Apple | `--theme apple` | 白底蓝调，极简科技风（默认）|
| 暖色 | `--theme warm` | 米白珊瑚，温暖人文风 |

---

## 输入数据说明

### `chat.json`

```json
[
  {"sender": "张三", "content": "今天天气真好！", "type": "text", "timestamp": 1704067200},
  {"sender": "李四", "content": "",               "type": "image", "timestamp": 1704067260}
]
```

支持的消息类型：`text` / `image` / `sticker` / `link` / `file` / `video` / `voice` / `call` / `reply` / `system` / `location`

### `top5.json`

由 `extract_topn.py` 自动生成，也可手动构造：

```json
{
  "group": "我的群",
  "charts": [
    {"chart": "总发言排行", "topn": [{"rank":1,"name":"张三","value":1280}, ...]},
    {"chart": "后起之秀",   "topn": [{"rank":1,"name":"新人甲","value_y":3.2,"value_x":45}]}
  ]
}
```

---

## 依赖

- Python 3.8+
- [jieba](https://github.com/fxsjy/jieba) — 中文分词

---

## License

MIT
