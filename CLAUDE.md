# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Generate a report (warm theme recommended)
python src/build_report.py <top3.json> <chat.json> -o report.html --theme warm

# Pass real total member count (chat data only captures speakers — silent/pre-data members are missed)
python src/build_report.py <top3.json> <chat.json> -o report.html --theme warm --members 150

# Extract top-N data from a Plotly HTML report
python src/extract_topn.py path/to/index.html   # → top3.json

# Convert exported WeChat Markdown to JSON
python md_to_json.py 群聊名称聊天记录.md         # → 群聊名称聊天记录.json
```

## Pipeline

```
wechat-cli export → .md
    ├── analyze_chat.py  → index.html (Plotly)
    │                          └── extract_topn.py → top3.json ─┐
    └── md_to_json.py → chat.json ───────────────────────────────┤
                                                       build_report.py
                                                           → report.html
```

## Architecture

### `src/build_report.py` — main report generator

Key functions:
- `main()` — CLI entry; computes all stats, renders HTML
- `make_css(C)` / `make_js()` — theme-aware CSS + JS string
- `leaderboard_html()` — drag-flip magnet tiles (Section 01)
- `portrait_tabs_html()` — tabbed card: 成员时间线 | 少言寡语 | 后起之秀 | 群组词频 | 个人词频
- `table_html()` — 综合榜单 sortable table (Section 02 left column)
- `svg_timeline()` — SVG timeline; >100d silent = hollow circle; hover shows daily img/link
- `svg_scatter_lurkers()` — bubble chart; x=span, y=total, size=daily_avg, colour=recency gradient
- `svg_scatter_stars()` — 后起之秀 scatter; x=days_late, y=daily_avg
- `make_group_prose()` — ~500-char narrative from group top words; top-3 highlighted
- `make_person_prose()` — ~100-char personal portrait; emoji sentence appended if emoji detected
- `peak_moment()` — finds busiest 1-hour slot; generates hover prose
- `compute_portraits()` / `make_portraits()` — per-person stats + lurker/star classification

**Stats bar (4 cells):**
| Cell | Default | Hover |
|------|---------|-------|
| 总消息数 | total_msg | 图片/链接/表情量 |
| 群成员 / 发言成员 | `--members N` → 真实总人数；未传 → 发言人数 | 活跃成员数（日均≥1条）· 有 --members 时显示占比 |
| 统计跨度（天） | total_span_days | 有消息天数 + 占比% |
| 全期日均发言 | daily_avg_total (÷total_span_days) | 有消息日日均 + 日均图/表情 |

Mouse-leave on any stat cell re-triggers the count-up animation (800 ms).

### `src/chat_utils.py` — tokenisation utilities

- `WECHAT_EMOJI` — set of 100+ WeChat emoji names: classic system set (微笑/强/再见…) + two extended batches (捂脸/嘿哈/吃瓜/加油/doge/裂开…)
- `top_words(texts, n)` — extracts `[emoji]` tokens via regex **before** jieba, so emoji like `[捂脸]` are counted as single tokens (stored as bare names without brackets)
- Emoji names are displayed with brackets in word-cloud badges: `[捂脸]`
- In `make_person_prose`, emoji words are separated from emotional/neutral words and generate a dedicated sentence: "常发[捂脸]、[强]等表情，辨识度十足。"

### `src/extract_topn.py` — Plotly HTML parser

Extracts top-N entries from each chart using bracket-counting JSON parser (`extract_json_at()`). Outputs `top3.json`.

## Themes

| Key | Style |
|-----|-------|
| `apple` | White + blue accent, minimal |
| `warm` | Off-white + coral accent, human |

Theme colours are in `THEMES` dict; passed as `C` throughout all functions.

## Data formats

**`top3.json`** — output of `extract_topn.py` (field is `top3` or `topn`):
```json
{"group": "群名", "charts": [{"chart": "总发言排行", "top3": [{"rank":1,"name":"张三","value":100}]}]}
```

**`chat.json`** — output of `md_to_json.py`:
```json
[{"sender":"张三","content":"今天天气好","type":"text","timestamp":1704067200}]
```
Internal fields after parsing: `ts` (datetime str), `date` (YYYY-MM-DD), `hour` (int), `msg_type`.

## Key constants in `build_report.py`

- `EMOTIONAL_WORDS` — 80+ words with emotional/evaluative weight; used to prioritise prose ordering
- `WECHAT_EMOJI` — imported from `chat_utils`; used in prose and badge display
- `LB_CATEGORIES` — leaderboard chart name patterns + display labels + tooltip descriptions
- `THEMES` — full colour palettes for `apple` and `warm`
