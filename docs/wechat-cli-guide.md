# 完整使用指南：从微信导出到 HTML 报告

本文档描述从 `wechat-cli` 导出聊天记录，到生成完整 HTML 报告的全流程，包括超过 10 万条消息的大群处理方案。

---

## 工具链全景

```
微信本地数据库
      │
      ▼
wechat-cli export          → 聊天记录.md
      │
      ▼
analyze_chat.py            → Plotly HTML 报告（含图表）
      │
      ▼
src/extract_topn.py        → top5.json（图表 Top-N 数据）
      │
      ├── src/build_report.py  ← chat.json（md_to_json.py 生成）
      ▼
    report.html            ← 最终交互式报告
```

---

## Step 1：安装 wechat-cli

```bash
# 推荐方式（需要 Node.js）
npm install -g @canghe_ai/wechat-cli

# 或 pip
pip install wechat-cli
```

---

## Step 2：初始化（首次执行一次）

```bash
# macOS/Linux（需要 sudo 提升权限读取进程内存）
sudo wechat-cli init

# Windows（在管理员终端中运行）
wechat-cli init
```

初始化会扫描微信进程内存提取 AES 加密密钥，保存到 `~/.wechat-cli/`。  
**微信必须保持运行状态。**

> **macOS 遇到 `task_for_pid failed`？**  
> 执行 `sudo codesign --force --sign - /Applications/WeChat.app`，重启微信后再试。

---

## Step 3：导出聊天记录为 Markdown

```bash
# 普通群聊（< 10 万条）
wechat-cli export "群聊名称" --format markdown --limit 9999999 --output 群聊名称聊天记录.md

# 同时导出多个群
wechat-cli export "群A" --format markdown --limit 9999999 --output A聊天记录.md
wechat-cli export "群B" --format markdown --limit 9999999 --output B聊天记录.md
```

导出的 Markdown 格式为：
```
- [2024-12-01 10:30] 张三: 今天天气真好
- [2024-12-01 10:31] 李四: [图片]
- [2024-12-01 10:32] 王五: 哈哈哈
```

---

## ⚠️ 超过 10 万条消息的大群处理

`wechat-cli export` 支持 `--offset` 参数，可以从第 N 条开始接续导出。  
**推荐做法：分批追加到同一个 MD 文件，不需要任何合并。**

```bash
# 第 1 批：前 99999 条
wechat-cli export "大群" --format markdown --limit 99999 --offset 0 \
    --output 大群聊天记录.md

# 第 2 批：从第 100000 条开始，追加到同一文件
wechat-cli export "大群" --format markdown --limit 99999 --offset 99999 \
    >> 大群聊天记录.md

# 第 3 批（如果还有）
wechat-cli export "大群" --format markdown --limit 99999 --offset 199998 \
    >> 大群聊天记录.md
```

> Windows CMD 用 `>>` 追加；PowerShell 用 `>> 大群聊天记录.md -Encoding UTF8`。

不确定总消息数？先查：

```bash
wechat-cli stats "大群" --format text
# 返回字段中包含总消息数
```

追加完成后，整个 `大群聊天记录.md` 就是完整记录，直接进入 Step 4。

### 备用方案：按时间段分段（适合只想分析特定时期）

```bash
# 只导出 2024 年
wechat-cli export "大群" --format markdown --limit 9999999 \
    --start-time "2024-01-01" --end-time "2024-12-31" \
    --output 大群_2024.md
```

---

## Step 4：生成 Plotly 图表报告（可选，为提取 Top-N 用）

如果你有基于 `analyze_chat.py` 生成的 Plotly HTML 报告，可以从中提取排行数据：

```bash
# 提取 Top 5（默认）
python src/extract_topn.py path/to/report.html

# 自定义 N
python src/extract_topn.py path/to/report.html --n 10

# 批量处理多个群
python src/extract_topn.py groupA/report.html groupB/report.html
```

输出 `top5.json` 到 HTML 同级目录。

---

## Step 5：生成最终 HTML 报告

### 先将 Markdown 转为 JSON（如果还没做）

```bash
python md_to_json.py 群聊名称聊天记录.md
# → 群聊名称聊天记录.json（即 chat.json）
```

### 生成报告

```bash
# Apple 主题（默认）
python src/build_report.py top5.json chat.json -o report.html

# 暖色主题
python src/build_report.py top5.json chat.json -o report.html --theme warm
```

---

## 完整示例（YAMATO快递群，约 3 万条）

```bash
# 1. 导出
wechat-cli export "YAMATO" --format markdown --limit 9999999 --output YAMATO聊天记录.md

# 2. 生成 Plotly 图表报告
python analyze_chat.py YAMATO聊天记录.md

# 3. 提取 Top-N 数据
python src/extract_topn.py html报告/YAMATO/report.html

# 4. 转 JSON
python md_to_json.py YAMATO聊天记录.md

# 5. 生成最终报告
python src/build_report.py html报告/YAMATO/top5.json YAMATO聊天记录.json \
    -o html报告/YAMATO/report_final.html
```

---

## 完整示例（超大群，约 15 万条）

```bash
# 1. 分年导出
wechat-cli export "超大群" --format markdown --limit 9999999 \
    --start-time "2022-01-01" --end-time "2022-12-31" --output 超大群_2022.md
wechat-cli export "超大群" --format markdown --limit 9999999 \
    --start-time "2023-01-01" --end-time "2023-12-31" --output 超大群_2023.md
wechat-cli export "超大群" --format markdown --limit 9999999 \
    --start-time "2024-01-01" --end-time "2024-12-31" --output 超大群_2024.md
wechat-cli export "超大群" --format markdown --limit 9999999 \
    --start-time "2025-01-01" --output 超大群_2025.md

# 2. 各段转 JSON
python md_to_json.py 超大群_2022.md 超大群_2023.md 超大群_2024.md 超大群_2025.md

# 3. 合并去重
python src/merge_chat.py 超大群_2022.json 超大群_2023.json \
    超大群_2024.json 超大群_2025.json -o chat.json

# 4. 生成 Plotly 报告（用合并后的 MD 文件）
cat 超大群_2022.md 超大群_2023.md 超大群_2024.md 超大群_2025.md > 超大群聊天记录.md
python analyze_chat.py 超大群聊天记录.md

# 5. 提取 Top-N
python src/extract_topn.py html报告/超大群/report.html

# 6. 生成最终报告
python src/build_report.py html报告/超大群/top5.json chat.json -o report.html
```

---

## 常见问题

### `wechat-cli init` 找不到微信进程？
确保微信桌面端正在运行，且已登录账号。Windows 上确认进程名是 `Weixin.exe`。

### 导出记录不完整？
微信本地数据库只保存**未清理过**的聊天记录。若此前手动清理过聊天记录，历史消息将不可找回。

### md_to_json.py 解析到 0 条？
检查 MD 文件前几行，格式应为 `- [YYYY-MM-DD HH:MM] 发送人: 内容`。  
不同版本的 wechat-cli export 可能有细微格式差异，检查 `LINE_RE` 正则是否匹配。

### analyze_chat.py 运行很慢？
安装依赖：`pip install pandas plotly jieba emoji`  
大文件（>5 万行）解析通常需要 30–60 秒，属正常范围。

### Windows 上乱码？
加 `PYTHONIOENCODING=utf-8` 前缀：
```bash
PYTHONIOENCODING=utf-8 python md_to_json.py xxx.md
```

---

## 依赖汇总

| 工具 | 安装 |
|------|------|
| wechat-cli | `npm install -g @canghe_ai/wechat-cli` |
| Python ≥ 3.10 | [python.org](https://python.org) |
| jieba | `pip install jieba` |
| pandas | `pip install pandas` |
| plotly | `pip install plotly` |
| emoji | `pip install emoji` |
