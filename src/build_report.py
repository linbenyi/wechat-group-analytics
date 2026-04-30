"""WeChat Group Chat Analytics — HTML Report Generator

Reads a topN.json (chart extracts) + a chat-records JSON, produces a
self-contained HTML report with:
  • Apple-style design system
  • Drag-and-reveal magnet leaderboard (Top 5 per category)
  • Sortable comprehensive table (Top 20, bold top-3 per column, hover %)
  • Portrait tabs: vanished members, lurkers, rising stars, timeline,
    word-cloud, per-person word frequency
  • Scroll-reveal animations, count-up numbers

Usage:
    python build_report.py <topN.json> <chat.json> [-o output.html] [--theme apple|warm]

Input JSON formats are described in examples/data_format.md.
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from chat_utils import top_words

# ── Themes ────────────────────────────────────────────────────────────────────

THEMES = {
    'apple': {
        'bg': '#F5F5F7', 'card': '#FFFFFF', 'border': '#D2D2D7',
        'warm': '#E8E8ED', 'accent': '#0071E3', 'accent2': '#0077ED',
        'text': '#1D1D1F', 'muted': '#6E6E73', 'ink': '#1D1D1F',
        'green': '#34C759', 'blue': '#0071E3', 'gold': '#FF9500',
        'purple': '#AF52DE', 'red': '#FF3B30', 'teal': '#5AC8FA',
    },
    'warm': {
        'bg': '#FAF7F0', 'card': '#FFFFFF', 'border': '#E4D8CB',
        'warm': '#F0E8DE', 'accent': '#C85A34', 'accent2': '#D97550',
        'text': '#1C1410', 'muted': '#7A6C62', 'ink': '#2C1810',
        'green': '#4A7A5C', 'blue': '#4A6E8A', 'gold': '#9A7A2C',
        'purple': '#6A5A8A', 'red': '#A0392B', 'teal': '#4A8A8A',
    },
}

MAGNET_BG = {
    'apple': ['#FFF3E5', '#E5F0FF', '#E5F9EC', '#F7E5FF', '#FFF8E5', '#FFE5E5'],
    'warm':  ['#FEF0E8', '#EBF3FB', '#ECF6F0', '#F2EEF8', '#FDFAED', '#FFF0F0'],
}
MAGNET_ROT = [-2.5, 1.8, -1.2, 2.1, -1.8, 1.4]

LB_CATEGORIES = [
    ('总发言王',  '总发言排行',   '条', 'accent',  '群内发送消息最多的成员——话最多、节奏最快的活跃担当。'),
    ('发图之王',  '发图最多',     '张', 'blue',    '发送图片/截图最多的成员，群内视觉内容的主要贡献者。'),
    ('链接达人',  '发链接最多',   '条', 'teal',    '分享链接最多的成员，把外部信息带进群的信息聚合者。'),
    ('熬夜冠军',  '夜猫子',       '条', 'purple',  '深夜 0–4 点发言最多的成员，习惯在夜深人静时活跃。'),
    ('早起之星',  '早起鸟',       '条', 'gold',    '早上 5–7 点发言最多的成员，清晨第一个打破沉寂。'),
    ('后起之秀',  '后起之秀',     '条', 'green',   '晚入群却活跃发言的新势力，后来者居上的代表。'),
]

DEFAULT_XIEHOUYU = '"群聊就是这样的——你以为大家都忘了，结果截图还存着呢。"'


# ── SVG helpers ───────────────────────────────────────────────────────────────

def svg_bar_h(items, C, width=480, bar_h=22, gap=8, color_key='muted', unit=''):
    color = C[color_key]
    if not items:
        return '<p style="color:var(--muted);font-size:.82rem">No data</p>'
    max_val = max(v for _, v in items) or 1
    bar_area = width - 148
    height = len(items) * (bar_h + gap) + 14
    rows = ''
    for i, (name, val) in enumerate(items):
        y = i * (bar_h + gap) + 7
        bw = int(bar_area * val / max_val)
        short = name[:10] + ('…' if len(name) > 10 else '')
        rows += (f'<text x="0" y="{y+bar_h*.72:.0f}" font-size="11" fill="{C["muted"]}">'
                 f'{short}</text>'
                 f'<rect x="143" y="{y}" width="{bw}" height="{bar_h}" rx="2"'
                 f' fill="{color}" opacity=".78"><title>{name}: {val:,}{unit}</title></rect>'
                 f'<text x="{143+bw+5}" y="{y+bar_h*.72:.0f}" font-size="10"'
                 f' fill="{C["accent"]}" font-weight="600">{val:,}</text>')
    return f'<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg">{rows}</svg>'


def svg_scatter(points, C, width=460, height=250, color_key='purple', xlabel='', ylabel=''):
    color = C[color_key]
    if not points:
        return '<p style="color:var(--muted);font-size:.82rem">No data</p>'
    xs = [p[1] for p in points]; ys = [p[2] for p in points]
    xr = max(xs) - min(xs) or 1; yr = max(ys) - min(ys) or 1
    pl, pb, pt, pr = 44, 38, 12, 12
    sx = lambda v: pl + (v - min(xs)) / xr * (width - pl - pr)
    sy = lambda v: height - pb - (v - min(ys)) / yr * (height - pb - pt)
    dots = ''
    for name, x, y, sz in points:
        cx, cy = sx(x), sy(y)
        r = 4 + sz * 7
        short = name[:7] + ('…' if len(name) > 7 else '')
        dots += (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{color}"'
                 f' opacity=".65" stroke="{C["card"]}" stroke-width="1.5">'
                 f'<title>{name}\n{xlabel}: {x}  {ylabel}: {y:,}</title></circle>'
                 f'<text x="{cx:.1f}" y="{cy-r-3:.1f}" font-size="9" fill="{C["text"]}"'
                 f' text-anchor="middle">{short}</text>')
    axes = (f'<line x1="{pl}" y1="{height-pb}" x2="{width-pr}" y2="{height-pb}" stroke="{C["border"]}"/>'
            f'<line x1="{pl}" y1="{pt}" x2="{pl}" y2="{height-pb}" stroke="{C["border"]}"/>'
            f'<text x="{(width+pl)//2}" y="{height-2}" font-size="9" fill="{C["muted"]}"'
            f' text-anchor="middle">{xlabel}</text>')
    return f'<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg">{axes}{dots}</svg>'


def svg_scatter_stars(points, C, width=460, height=270, color_key='green',
                      xmin=30, xmax=330, ref_x=100):
    """Linear-scale scatter: x = days-late (fixed range), y = daily-avg messages."""
    color = C[color_key]
    if not points:
        return '<p style="color:var(--muted);font-size:.82rem">No data</p>'
    pl, pb, pt, pr = 52, 42, 16, 16
    ys = [p[2] for p in points]
    ymax = max(ys) * 1.15 or 1
    sx = lambda v: pl + (v - xmin) / (xmax - xmin) * (width - pl - pr)
    sy = lambda v: height - pb - v / ymax * (height - pb - pt)

    raw_step = ymax / 5
    mag = 10 ** math.floor(math.log10(raw_step)) if raw_step > 0 else 1
    step = max(mag, round(raw_step / mag) * mag)

    grid = ''
    for xv in range(xmin, xmax + 1, 60):
        gx = sx(xv)
        grid += (f'<line x1="{gx:.1f}" y1="{pt}" x2="{gx:.1f}" y2="{height-pb}"'
                 f' stroke="{C["border"]}" stroke-width="0.8"/>'
                 f'<text x="{gx:.1f}" y="{height-pb+13}" font-size="9" fill="{C["muted"]}"'
                 f' text-anchor="middle" font-family="ui-monospace,monospace">{xv}</text>')
    yv = step
    while yv <= ymax:
        gy = sy(yv)
        lbl = f'{yv:.0f}' if yv >= 1 else f'{yv:.1f}'
        grid += (f'<line x1="{pl}" y1="{gy:.1f}" x2="{width-pr}" y2="{gy:.1f}"'
                 f' stroke="{C["border"]}" stroke-width="0.8"/>'
                 f'<text x="{pl-5}" y="{gy+3:.1f}" font-size="9" fill="{C["muted"]}"'
                 f' text-anchor="end" font-family="ui-monospace,monospace">{lbl}</text>')
        yv += step
    if xmin <= ref_x <= xmax:
        gxr = sx(ref_x)
        grid += (f'<line x1="{gxr:.1f}" y1="{pt}" x2="{gxr:.1f}" y2="{height-pb}"'
                 f' stroke="{C["accent"]}" stroke-width="1.2" opacity=".4" stroke-dasharray="4,3"/>'
                 f'<text x="{gxr:.1f}" y="{height-pb+13}" font-size="9" fill="{C["accent"]}"'
                 f' text-anchor="middle" font-weight="700">{ref_x}</text>')
    axes = (f'<line x1="{pl}" y1="{height-pb}" x2="{width-pr}" y2="{height-pb}"'
            f' stroke="{C["border"]}" stroke-width="1.2"/>'
            f'<line x1="{pl}" y1="{pt}" x2="{pl}" y2="{height-pb}"'
            f' stroke="{C["border"]}" stroke-width="1.2"/>'
            f'<text x="{(width+pl)//2}" y="{height-1}" font-size="9" fill="{C["muted"]}"'
            f' text-anchor="middle">Days since first message (log ref {ref_x})</text>'
            f'<text x="10" y="{(height+pt)//2}" font-size="9" fill="{C["muted"]}"'
            f' text-anchor="middle" transform="rotate(-90,10,{(height+pt)//2})">Daily avg</text>')
    dots = ''
    for name, late, daily_avg, sz in points:
        cx = min(max(sx(late), pl), width - pr)
        cy = min(max(sy(daily_avg), pt), height - pb)
        r = 4 + sz * 7
        short = name[:7] + ('…' if len(name) > 7 else '')
        dots += (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{color}"'
                 f' opacity=".68" stroke="{C["card"]}" stroke-width="1.5">'
                 f'<title>{name}\nDays late: {late}\nDaily avg: {daily_avg:.1f}</title></circle>'
                 f'<text x="{cx:.1f}" y="{cy-r-3:.1f}" font-size="9" fill="{C["text"]}"'
                 f' text-anchor="middle">{short}</text>')
    return f'<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg">{grid}{axes}{dots}</svg>'


def svg_timeline(events, C, width=460):
    if not events:
        return '<p style="color:var(--muted);font-size:.82rem">No data</p>'
    h = len(events) * 44 + 14
    items = ''
    for i, (label, sub) in enumerate(events):
        y = i * 44 + 24
        conn = (f'<line x1="14" y1="{y+5}" x2="14" y2="{y+38}" stroke="{C["border"]}" stroke-width="1.5"/>'
                if i < len(events) - 1 else '')
        items += (f'<circle cx="14" cy="{y}" r="4" fill="{C["accent"]}" opacity=".85"/>{conn}'
                  f'<text x="30" y="{y+4}" font-size="12" font-weight="600" fill="{C["text"]}">{label}</text>'
                  f'<text x="30" y="{y+18}" font-size="10" fill="{C["muted"]}">{sub}</text>')
    return f'<svg viewBox="0 0 {width} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">{items}</svg>'


# ── Data computation ──────────────────────────────────────────────────────────

def compute_portraits(messages):
    stats = defaultdict(lambda: {
        'total': 0, 'image': 0, 'link': 0,
        'night': 0, 'early': 0, 'first': None, 'last': None,
    })
    for m in messages:
        s = m['sender']
        if s == 'system':
            continue
        d = stats[s]
        d['total'] += 1
        if m['msg_type'] == 'image': d['image'] += 1
        if m['msg_type'] == 'link':  d['link'] += 1
        if m['hour'] <= 4:           d['night'] += 1
        if 5 <= m['hour'] <= 7:      d['early'] += 1
        ts = m['ts']
        if d['first'] is None or ts < d['first']: d['first'] = ts
        if d['last']  is None or ts > d['last']:  d['last']  = ts

    valid = [v for v in stats.values() if v['first']]
    if not valid:
        return []
    gf = min(v['first'] for v in valid)
    gl = max(v['last']  for v in valid)
    rows = []
    for name, d in stats.items():
        if not d['first']:
            continue
        span   = (datetime.strptime(d['last'],  '%Y-%m-%d %H:%M') -
                  datetime.strptime(d['first'], '%Y-%m-%d %H:%M')).days
        late   = (datetime.strptime(d['first'], '%Y-%m-%d %H:%M') -
                  datetime.strptime(gf,         '%Y-%m-%d %H:%M')).days
        silent = (datetime.strptime(gl,         '%Y-%m-%d %H:%M') -
                  datetime.strptime(d['last'],  '%Y-%m-%d %H:%M')).days
        rows.append({
            'name': name, 'total': d['total'], 'image': d['image'],
            'link': d['link'], 'night': d['night'], 'early': d['early'],
            'span': span, 'late': late, 'silent': silent,
            'first': d['first'][:10], 'last': d['last'][:10],
        })
    return rows


def make_portraits(rows, vanish_min=10, vanish_days=180,
                   lurk_max=50, lurk_span=180,
                   star_late=30, star_total=20, limit=20):
    lurkers  = sorted([r for r in rows if r['total'] <= lurk_max and r['span'] >= lurk_span],
                      key=lambda r: r['span'], reverse=True)[:limit]
    vanished = sorted([r for r in rows if r['total'] >= vanish_min and r['silent'] >= vanish_days],
                      key=lambda r: r['silent'], reverse=True)[:limit]
    stars    = sorted([r for r in rows if r['late'] >= star_late and r['total'] >= star_total],
                      key=lambda r: r['total'], reverse=True)[:limit]
    return lurkers, vanished, stars


def peak_moment(messages, peak_chart):
    if not peak_chart:
        return '', 0, ''
    peak_time  = peak_chart[0]['name']
    peak_count = peak_chart[0].get('value', 0)
    hour_prefix = peak_time[:13]
    peak_msgs = [m for m in messages
                 if m['ts'].startswith(hour_prefix) and m['msg_type'] == 'text']
    words = top_words([m['content'] for m in peak_msgs], 8)
    topic = '热烈讨论'
    kw_map = [
        (['红包', '抢', '领'],          '抢红包'),
        (['公告', '通知', '规则'],       '群公告'),
        (['活动', '报名', '福利'],       '活动通知'),
        (['哈哈', '笑', '梗', '整'],     '整活'),
        (['新闻', '热搜', '爆'],         '时事讨论'),
        (['工作', '招聘', '求职'],       '职场话题'),
    ]
    all_w = {w for w, _ in words}
    for kws, label in kw_map:
        if any(k in all_w or any(k in w for w in all_w) for k in kws):
            topic = label
            break
    return peak_time, peak_count, topic


# ── HTML fragment builders ────────────────────────────────────────────────────

def word_html(messages):
    texts = [m['content'] for m in messages if m['msg_type'] == 'text']
    words = top_words(texts, 40)
    if not words:
        return ''
    mc = words[0][1]
    C_accent = 'var(--accent)'
    C_accent2 = 'var(--accent2)'
    C_muted = 'var(--muted)'
    badges = ''
    for w, c in words:
        p = c / mc
        size = 0.76 + p * 0.92
        op   = 0.40 + p * 0.60
        col  = C_accent if p > 0.6 else (C_accent2 if p > 0.3 else C_muted)
        badges += (f'<span class="wbadge" style="font-size:{size:.2f}rem;color:{col};opacity:{op:.2f}"'
                   f' title="{c} 次">{w}</span>')
    return f'<div class="word-cloud">{badges}</div>'


def person_words_html(messages, portrait_rows):
    top20 = [r['name'] for r in sorted(portrait_rows, key=lambda r: r['total'], reverse=True)[:20]]
    by_sender = defaultdict(list)
    for m in messages:
        if m['msg_type'] == 'text' and m['sender'] in top20:
            by_sender[m['sender']].append(m['content'])
    items = []
    for name in top20:
        words = top_words(by_sender.get(name, []), 8)
        if not words:
            continue
        mc = words[0][1]
        badges = ''
        for w, c in words[:8]:
            p = c / mc
            size = 0.78 + p * 0.50
            op   = 0.55 + p * 0.45
            badges += (f'<span class="wbadge" style="font-size:{size:.2f}rem;'
                       f'color:var(--accent);opacity:{op:.2f}" title="{c} 次">{w}</span> ')
        short = name[:10] + ('…' if len(name) > 10 else '')
        items.append(f'<div class="pw-row"><span class="pw-name" title="{name}">{short}</span>'
                     f'<span class="pw-words">{badges}</span></div>')
    return '<div class="pw-list">' + ''.join(items) + '</div>'


def leaderboard_html(charts, C, magnet_bg, xiehouyu_text=DEFAULT_XIEHOUYU):
    def get(kw):
        for c in charts:
            if kw in c['chart']:
                return c.get('topn', c.get('top5', c.get('top3', [])))
        return []

    cards = ''
    for i, (title, chart_kw, unit, color_key, desc) in enumerate(LB_CATEGORIES):
        data = get(chart_kw)
        if not data:
            continue
        bg  = magnet_bg[i % len(magnet_bg)]
        rot = MAGNET_ROT[i % len(MAGNET_ROT)]
        color = C[color_key]
        rows = ''
        for j, item in enumerate(data[:5]):
            name = item.get('name', '')
            val  = item.get('value', item.get('value_y', ''))
            rows += (f'<div class="lb-row">'
                     f'<span class="lb-rank">{j+1}</span>'
                     f'<span class="lb-name">{name}</span>'
                     f'<span class="lb-val" style="color:{color}">{val:,}&thinsp;{unit}</span>'
                     f'</div>')
        cards += (f'<div class="magnet-card" data-desc="{desc}" data-rot="{rot}" style="background:{bg}">'
                  f'<div class="lb-title-wrap"><div class="lb-title">{title}</div>'
                  f'<div class="honor-tag"></div></div>'
                  f'{rows}'
                  f'<div class="click-guide">✦ 点击揭示 ✦</div></div>')
    return (f'<div class="magnet-board scale-reveal">{cards}'
            f'<div class="xiehouyu">{xiehouyu_text}</div></div>')


def table_html(portrait_rows, total_msg=1):
    top20 = sorted(portrait_rows, key=lambda r: r['total'], reverse=True)[:20]
    cols = ['total', 'image', 'link', 'night', 'early']
    top3 = {col: set(sorted({r[col] for r in top20 if r[col] > 0}, reverse=True)[:3])
            for col in cols}

    def fmt(v): return f'{v:,}' if v else '-'

    tbody = ''
    for i, r in enumerate(top20):
        cells = f'<td style="color:var(--muted)">{i+1}</td><td>{r["name"]}</td>'
        for col in cols:
            v = r[col]
            bold = 'font-weight:700;' if v in top3[col] and v > 0 else ''
            pct = v / total_msg * 100 if total_msg else 0
            title = f' title="占总发言 {pct:.1f}%"' if v else ''
            cells += f'<td style="{bold}"{title}>{fmt(v)}</td>'
        tbody += f'<tr>{cells}</tr>'

    return (f'<div class="tbl-scroll"><table id="mt" class="dtbl"><thead><tr>'
            f'<th onclick="sortTbl(\'mt\',0,\'n\')">#</th>'
            f'<th onclick="sortTbl(\'mt\',1,\'s\')">昵称</th>'
            f'<th onclick="sortTbl(\'mt\',2,\'n\')">发言</th>'
            f'<th onclick="sortTbl(\'mt\',3,\'n\')">图</th>'
            f'<th onclick="sortTbl(\'mt\',4,\'n\')">链接</th>'
            f'<th onclick="sortTbl(\'mt\',5,\'n\')">深夜</th>'
            f'<th onclick="sortTbl(\'mt\',6,\'n\')">早起</th>'
            f'</tr></thead><tbody>{tbody}</tbody></table></div>')


def portrait_tabs_html(portrait_rows, messages, C):
    lurkers, vanished, stars = make_portraits(portrait_rows)

    svg1 = svg_bar_h([(r['name'], r['silent']) for r in vanished], C, color_key='muted', unit='d')
    mt = max((r['total'] for r in lurkers), default=1)
    svg2 = svg_scatter([(r['name'], r['span'], r['total'], r['total']/mt) for r in lurkers],
                       C, color_key='purple', xlabel='Active span (days)', ylabel='Messages')
    ms = max((r['total'] / max(r['span'], 1) for r in stars), default=1)
    svg3 = svg_scatter_stars(
        [(r['name'], r['late'], r['total']/max(r['span'],1), (r['total']/max(r['span'],1))/ms)
         for r in stars], C, color_key='green')
    tl = [(r['name'], f"Last seen {r['last']} · silent {r['silent']}d") for r in vanished[:8]]
    svg_tl = svg_timeline(tl, C)
    wh = word_html(messages)
    pw = person_words_html(messages, portrait_rows)

    nv, nl, ns = len(vanished), len(lurkers), len(stars)
    def tc(n): return f'<span class="tab-count">{n}</span>' if n else ''

    return f"""<div class="portrait-tabs">
  <div class="tab-bar">
    <button class="tab-btn active" onclick="showTab(this,'tp-van')">消失的人{tc(nv)}</button>
    <button class="tab-btn" onclick="showTab(this,'tp-lurk')">少言寡语{tc(nl)}</button>
    <button class="tab-btn" onclick="showTab(this,'tp-star')">后起之秀{tc(ns)}</button>
    <button class="tab-btn" onclick="showTab(this,'tp-tl')">时间线</button>
    <button class="tab-btn" onclick="showTab(this,'tp-word')">词频</button>
    <button class="tab-btn" onclick="showTab(this,'tp-pw')">个人词频</button>
  </div>
  <div id="tp-van" class="tab-panel active">
    <div class="p-card"><h3>消失的人</h3>
      <span class="p-count">{nv} members · ≥10 msgs, silent ≥180d</span>
      <div class="svg-container">{svg1}</div></div>
  </div>
  <div id="tp-lurk" class="tab-panel">
    <div class="p-card"><h3>少言寡语者</h3>
      <span class="p-count">{nl} members · ≤50 msgs, span ≥180d</span>
      <div class="svg-container">{svg2}</div></div>
  </div>
  <div id="tp-star" class="tab-panel">
    <div class="p-card"><h3>后起之秀</h3>
      <span class="p-count">{ns} members · joined ≥30d late, ≥20 msgs · dashed = 100d ref</span>
      <div class="svg-container">{svg3}</div></div>
  </div>
  <div id="tp-tl" class="tab-panel">
    <div class="p-card"><h3>最后现身时间线</h3>
      <span class="p-count">Last appearance of vanished members</span>
      <div class="svg-container">{svg_tl}</div></div>
  </div>
  <div id="tp-word" class="tab-panel">
    <div class="p-card"><h3>词频</h3>
      <span class="p-count">Hover a word to see its count</span>
      {wh}</div>
  </div>
  <div id="tp-pw" class="tab-panel">
    <div class="p-card"><h3>个人词频</h3>
      <span class="p-count">Top-20 speakers · top-8 personal words · hover for count</span>
      <div class="svg-container" style="display:block">{pw}</div></div>
  </div>
</div>"""


# ── CSS & JS (theme-aware) ────────────────────────────────────────────────────

def make_css(C):
    return f"""
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400;1,500&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
:root{{
  --bg:{C['bg']};--card:{C['card']};--border:{C['border']};
  --warm:{C['warm']};--accent:{C['accent']};--accent2:{C['accent2']};
  --text:{C['text']};--muted:{C['muted']};--ink:{C['ink']};
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);
  font-family:'Noto Sans SC','PingFang SC','-apple-system','Helvetica Neue',sans-serif;
  font-size:14px;line-height:1.7;-webkit-font-smoothing:antialiased}}
p{{text-wrap:pretty}}h1,h2,h3{{text-wrap:balance}}
*{{scrollbar-width:thin;scrollbar-color:var(--border) transparent}}

@keyframes fadeInUp{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes scaleIn{{from{{opacity:0;transform:scale(.95)}}to{{opacity:1;transform:scale(1)}}}}
.reveal{{opacity:0}}.reveal.visible{{animation:fadeInUp .8s cubic-bezier(.2,.8,.2,1) forwards}}
.scale-reveal{{opacity:0}}.scale-reveal.visible{{animation:scaleIn .8s cubic-bezier(.2,.8,.2,1) forwards}}
.delay-1{{animation-delay:.1s}}.delay-2{{animation-delay:.2s}}
.delay-3{{animation-delay:.3s}}.delay-4{{animation-delay:.4s}}

header{{background:var(--warm);color:var(--ink);padding:52px 56px 44px;position:relative;overflow:hidden;border-bottom:1px solid var(--border)}}
.h-eyebrow{{font-size:.63rem;letter-spacing:.22em;text-transform:uppercase;color:rgba(0,0,0,.32);margin-bottom:14px}}
header h1{{font-family:'EB Garamond',serif;font-size:clamp(1.9rem,4vw,3.1rem);font-weight:400;line-height:1.14;max-width:800px}}
header h1 em{{font-style:italic;color:var(--accent)}}
.h-rule{{width:36px;height:1.5px;background:var(--accent);margin:22px 0}}
.h-meta{{display:flex;gap:28px;flex-wrap:wrap;font-size:.78rem;color:rgba(0,0,0,.44)}}
.h-meta strong{{color:rgba(0,0,0,.78);font-weight:400}}
.h-peak{{position:absolute;bottom:24px;right:56px;text-align:right;opacity:.22;pointer-events:none}}
.h-peak-label{{font-size:.58rem;letter-spacing:.15em;text-transform:uppercase;display:block;margin-bottom:2px}}
.h-peak-num{{font-family:'EB Garamond',serif;font-size:3.2rem;font-weight:400;line-height:1;color:var(--accent);display:block}}
.h-peak-rest{{font-size:.68rem;display:block;margin-top:4px}}

.stats-bar{{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--border);background:var(--card)}}
.stat-cell{{padding:26px 22px 22px;border-right:1px solid var(--border);transition:background .15s;cursor:default}}
.stat-cell:last-child{{border-right:none}}
.stat-cell:hover{{background:var(--warm)}}
.stat-n{{font-family:'EB Garamond',serif;font-size:2.5rem;font-weight:400;color:var(--accent);line-height:1;margin-bottom:5px;font-variant-numeric:tabular-nums}}
.stat-l{{font-size:.64rem;color:var(--muted);text-transform:uppercase;letter-spacing:.13em}}

.section{{padding:44px 56px 0}}
.section-head{{display:flex;align-items:baseline;gap:13px;padding-bottom:11px;border-bottom:1px solid var(--border);margin-bottom:9px}}
.section-num{{font-size:.61rem;color:var(--muted);letter-spacing:.1em;flex-shrink:0;opacity:.5;font-family:ui-monospace,monospace}}
.section-head h2{{font-family:'EB Garamond',serif;font-size:1.32rem;font-weight:400}}
.sec-desc{{font-size:.78rem;color:var(--muted);margin:7px 0 18px;max-width:560px}}

.magnet-board{{position:relative;background:var(--warm);border-radius:10px;padding:16px;min-height:260px;border:1px solid var(--border);overflow:hidden}}
.magnet-card{{position:absolute;width:185px;background:var(--card);border-radius:4px;padding:13px 15px 10px;
  box-shadow:2px 3px 10px rgba(0,0,0,.10),0 1px 3px rgba(0,0,0,.06);
  cursor:grab;user-select:none;
  transition:box-shadow .2s,transform .2s,left .4s cubic-bezier(.2,.8,.2,1),top .4s cubic-bezier(.2,.8,.2,1);
  border:1px solid var(--border);z-index:1}}
.magnet-card:hover{{box-shadow:4px 8px 22px rgba(0,0,0,.16);z-index:20}}
.magnet-card.dragging{{cursor:grabbing!important;box-shadow:6px 12px 28px rgba(0,0,0,.22);z-index:100;transition:none!important}}
.magnet-card.active-center{{z-index:50;transform:scale(1.05)!important}}
.lb-title-wrap{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
.lb-title{{font-size:.61rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.13em;opacity:.75}}
.honor-tag{{font-size:.6rem;color:var(--accent);font-weight:700;opacity:0;transition:opacity .5s}}
.honor-tag.show{{opacity:1}}
.click-guide{{text-align:center;font-size:.58rem;color:var(--accent);margin-top:8px;opacity:.5;
  border-top:1px dashed var(--border);padding-top:4px;cursor:pointer;animation:pulse 2s infinite}}
@keyframes pulse{{0%{{opacity:.3}}50%{{opacity:.8}}100%{{opacity:.3}}}}
.magnet-card.revealed .click-guide{{display:none}}
.lb-row{{display:flex;align-items:center;padding:4px 0;border-bottom:1px solid rgba(0,0,0,.06)}}
.lb-row:last-child{{border-bottom:none}}
.lb-rank{{font-family:'EB Garamond',serif;font-size:.9rem;color:var(--muted);width:15px;flex-shrink:0;opacity:.5}}
.lb-name{{flex:1;font-size:.82rem;padding:0 6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;visibility:hidden}}
.magnet-card.revealed .lb-name{{visibility:visible}}
.lb-val{{font-size:.76rem;font-weight:600;flex-shrink:0;font-variant-numeric:tabular-nums}}
.xiehouyu{{position:absolute;bottom:10px;right:20px;font-size:.85rem;color:var(--accent);font-style:italic;opacity:0;transition:opacity .5s;pointer-events:none}}
.xiehouyu.show{{opacity:.7}}

.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:stretch}}
.col-label{{font-size:.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:.12em;margin-bottom:10px;opacity:.7}}
.tbl-scroll{{overflow-y:auto;height:450px;border-radius:8px;border:1px solid var(--border)}}
table.dtbl{{width:100%;border-collapse:collapse;font-size:.78rem;background:var(--card)}}
table.dtbl thead th{{position:sticky;top:0;z-index:2;padding:9px 12px;text-align:left;
  cursor:pointer;user-select:none;white-space:nowrap;font-weight:700;color:var(--muted);
  font-size:.61rem;text-transform:uppercase;letter-spacing:.1em;
  background:var(--warm);border-bottom:1px solid var(--border)}}
table.dtbl td{{padding:7px 12px;border-bottom:1px solid rgba(0,0,0,.05)}}
table.dtbl td:not(:first-child):not(:nth-child(2)){{color:var(--accent);font-variant-numeric:tabular-nums}}

.portrait-tabs{{display:flex;flex-direction:column;height:450px}}
.tab-bar{{display:flex;border-bottom:1px solid var(--border);flex-wrap:wrap}}
.tab-btn{{background:none;border:none;border-bottom:2px solid transparent;margin-bottom:-1px;
  padding:8px 14px;font-size:.78rem;font-family:'Noto Sans SC',sans-serif;
  color:var(--muted);cursor:pointer;transition:color .12s;white-space:nowrap}}
.tab-btn:hover{{color:var(--accent)}}
.tab-btn.active{{color:var(--accent);border-bottom-color:var(--accent)}}
.tab-panel{{display:none;padding:14px 0 0;flex:1;overflow:hidden}}
.tab-panel.active{{display:flex;flex-direction:column}}
.p-card{{background:var(--card);border:1px solid var(--border);border-radius:8px;
  padding:18px 20px 14px;flex:1;display:flex;flex-direction:column;overflow:hidden}}
.p-card h3{{font-family:'EB Garamond',serif;font-size:.95rem;font-weight:400;margin-bottom:3px}}
.p-count{{display:block;font-size:.7rem;color:var(--accent);font-style:italic;margin-bottom:6px}}
.svg-container{{flex:1;overflow-y:auto;border:1px solid rgba(0,0,0,.06);border-radius:4px;
  padding:12px;display:flex;justify-content:center;align-items:flex-start}}
.p-card svg{{width:100%;height:auto;max-width:440px}}
.word-cloud{{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;line-height:1.8;padding:6px 0;flex:1;overflow-y:auto}}
.wbadge{{padding:1px 0;cursor:default;transition:opacity .12s;border-bottom:1.2px solid transparent;white-space:nowrap;display:inline-block}}
.wbadge:hover{{border-bottom-color:var(--accent)}}
.tab-count{{font-size:.6rem;opacity:.5;margin-left:3px}}
.pw-list{{width:100%}}
.pw-row{{display:flex;align-items:baseline;gap:10px;padding:5px 0;border-bottom:1px solid rgba(0,0,0,.06)}}
.pw-row:last-child{{border-bottom:none}}
.pw-name{{font-size:.74rem;color:var(--muted);min-width:84px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.pw-words{{flex:1;line-height:1.9}}

footer{{margin-top:64px;padding:24px 56px;border-top:1px solid var(--border);
  display:flex;justify-content:center;font-size:.68rem;color:var(--muted);opacity:.7;font-style:italic}}
@media(max-width:960px){{
  .two-col{{grid-template-columns:1fr}}
  header,.section{{padding-left:24px;padding-right:24px}}
  .stats-bar{{grid-template-columns:repeat(2,1fr)}}
  .h-peak{{display:none}}
  .tbl-scroll,.portrait-tabs{{height:auto;min-height:400px}}
}}"""


JS = r"""
function showTab(btn, id) {
  var w = btn.closest('.portrait-tabs');
  w.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  w.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(id).classList.add('active');
}
function sortTbl(id, col, type) {
  var t = document.getElementById(id), tb = t.tBodies[0];
  var asc = t.dataset.col == col && t.dataset.asc == '1';
  Array.from(tb.rows).sort(function(a, b) {
    var av = a.cells[col].innerText.trim(), bv = b.cells[col].innerText.trim();
    if (type === 'n') {
      av = parseFloat(av.replace(/,/g,'').replace(/-/g,'0'))||0;
      bv = parseFloat(bv.replace(/,/g,'').replace(/-/g,'0'))||0;
      return asc ? av-bv : bv-av;
    }
    return asc ? av.localeCompare(bv,'zh') : bv.localeCompare(av,'zh');
  }).forEach(r => tb.appendChild(r));
  t.dataset.col = col; t.dataset.asc = asc ? '0' : '1';
}
(function() {
  var board = document.querySelector('.magnet-board');
  if (!board) return;
  var cards = Array.from(board.querySelectorAll('.magnet-card'));
  var xiehouyu = board.querySelector('.xiehouyu');
  var CARD_W = 185, CARD_H = 165, GAP_X = 18, GAP_Y = 16, PAD = 16;
  var order = cards.map((_, i) => i);
  var honors = ["荣誉会长","活跃元勋","资深专家","核心贡献","潜力之星","忠实铁粉"];

  function layout() {
    var bw = board.offsetWidth - PAD * 2;
    var cols = Math.max(1, Math.floor((bw + GAP_X) / (CARD_W + GAP_X)));
    board.style.minHeight = (PAD*2 + Math.ceil(cards.length/cols)*(CARD_H+GAP_Y)) + 'px';
    order.forEach((ci, pi) => {
      var card = cards[ci];
      if (card.classList.contains('dragging')) return;
      card.style.left = (PAD + (pi%cols)*(CARD_W+GAP_X)) + 'px';
      card.style.top  = (PAD + Math.floor(pi/cols)*(CARD_H+GAP_Y)) + 'px';
      card.style.transform = 'rotate(' + (parseFloat(card.dataset.rot)||0) + 'deg)';
    });
  }
  layout(); window.addEventListener('resize', layout);

  var tip = document.createElement('div');
  tip.style.cssText = 'position:fixed;background:rgba(0,0,0,.85);color:#fff;padding:7px 12px;border-radius:6px;font-size:.74rem;max-width:220px;pointer-events:none;z-index:9999;opacity:0;transition:opacity .18s;line-height:1.5';
  document.body.appendChild(tip);

  cards.forEach((card, i) => {
    card.addEventListener('mouseenter', () => { if(card.dataset.desc){tip.textContent=card.dataset.desc;tip.style.opacity='1';} });
    card.addEventListener('mousemove', e => { tip.style.left=(e.clientX+14)+'px'; tip.style.top=(e.clientY+14)+'px'; });
    card.addEventListener('mouseleave', () => tip.style.opacity='0');
    card.addEventListener('mousedown', function(e) {
      e.preventDefault();
      var rect=card.getBoundingClientRect(), br=board.getBoundingClientRect();
      var sx=e.clientX, sy=e.clientY, sl=rect.left-br.left, st=rect.top-br.top;
      card.classList.add('dragging');
      function mv(me) {
        var dx=me.clientX-sx, dy=me.clientY-sy;
        card.style.left=(sl+dx)+'px'; card.style.top=(st+dy)+'px';
        card.style.transform='rotate(0deg) scale(1.05)';
        var bw=board.offsetWidth-PAD*2, cols=Math.max(1,Math.floor((bw+GAP_X)/(CARD_W+GAP_X)));
        var np=Math.min(cards.length-1,Math.floor((st+dy+CARD_H/2-PAD)/(CARD_H+GAP_Y))*cols+Math.max(0,Math.min(cols-1,Math.floor((sl+dx+CARD_W/2-PAD)/(CARD_W+GAP_X)))));
        var cp=order.indexOf(i); if(np!==cp){order.splice(cp,1);order.splice(np,0,i);layout();}
      }
      function up() {
        card.classList.remove('dragging');
        document.removeEventListener('mousemove',mv); document.removeEventListener('mouseup',up);
        if(!card.classList.contains('revealed')){
          card.classList.add('revealed');
          var tag=card.querySelector('.honor-tag');
          tag.textContent=honors[Math.floor(Math.random()*honors.length)];
          tag.classList.add('show'); setTimeout(()=>tag.classList.remove('show'),3000);
        }
        cards.forEach(c=>c.classList.remove('active-center')); card.classList.add('active-center'); layout();
        if(xiehouyu && cards.every(c=>c.classList.contains('revealed'))) xiehouyu.classList.add('show');
      }
      document.addEventListener('mousemove',mv); document.addEventListener('mouseup',up);
    });
  });

  function countUp(el, end, ms) {
    var s=performance.now();
    (function tick(now){
      var t=Math.min((now-s)/ms,1), ease=1-Math.pow(2,-10*t);
      el.textContent=Math.floor(ease*end).toLocaleString('zh-CN');
      if(t<1) requestAnimationFrame(tick); else el.textContent=end.toLocaleString('zh-CN');
    })(s);
  }
  var io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)e.target.classList.add('visible');}),{threshold:.1});
  document.querySelectorAll('.reveal,.scale-reveal').forEach(el=>io.observe(el));
  var co=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){var v=parseInt(e.target.dataset.val);if(!isNaN(v))countUp(e.target,v,1200);co.unobserve(e.target);}}),{threshold:.4});
  document.querySelectorAll('.stat-n[data-val]').forEach(el=>co.observe(el));
})();
"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Generate a WeChat group chat analytics HTML report.')
    parser.add_argument('topn_json', help='Path to topN.json (chart extracts from extract_topn.py)')
    parser.add_argument('chat_json', help='Path to chat-records JSON')
    parser.add_argument('-o', '--output', default='', help='Output HTML path (default: alongside topN.json)')
    parser.add_argument('--theme', choices=['apple', 'warm'], default='apple', help='Colour theme (default: apple)')
    args = parser.parse_args()

    topn_path = Path(args.topn_json)
    chat_path = Path(args.chat_json)
    out_path  = Path(args.output) if args.output else topn_path.parent / 'report.html'

    topn_data = json.loads(topn_path.read_text('utf-8'))
    charts    = topn_data.get('charts', [])

    chat_data = json.loads(chat_path.read_text('utf-8'))
    messages  = chat_data.get('messages', [])
    group     = chat_data.get('group', topn_data.get('group', 'Group'))
    total_msg = chat_data.get('total', len(messages))
    xiehouyu  = chat_data.get('xiehouyu', DEFAULT_XIEHOUYU)

    C  = THEMES[args.theme]
    bg = MAGNET_BG[args.theme]

    senders = {m['sender'] for m in messages if m['sender'] != 'system'}
    n_members = len(senders)
    dates = sorted({m['date'] for m in messages if 'date' in m and m['sender'] != 'system'})
    n_active  = len(dates)
    date_start, date_end = (dates[0], dates[-1]) if dates else ('', '')
    daily_avg = round(total_msg / n_active) if n_active else 0

    def get_chart(kw):
        return next((c.get('topn', c.get('top5', c.get('top3', [])))
                     for c in charts if kw in c['chart']), [])

    peak_time, peak_count, topic = peak_moment(messages, get_chart('最激烈'))
    pc_fmt = f'{peak_count:,}' if peak_count else '—'
    h_peak = (f'<div class="h-peak"><span class="h-peak-label">历史峰值</span>'
              f'<span class="h-peak-num">{pc_fmt}</span>'
              f'<span class="h-peak-rest">条/小时·{topic}·{peak_time}</span></div>') if peak_count else ''

    portrait_rows = compute_portraits(messages)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{group} — 聊天数据分析报告</title>
<style>{make_css(C)}</style>
</head>
<body>

<header class="reveal">
  <div class="h-eyebrow">Chat Analytics · wechat-group-analytics</div>
  <h1><em>{group}</em><br>聊天数据分析报告</h1>
  <div class="h-rule"></div>
  <div class="h-meta">
    <span><strong>{date_start}</strong> — <strong>{date_end}</strong></span>
    <span><strong>{total_msg:,}</strong> 条消息</span>
    <span><strong>{n_members:,}</strong> 位成员</span>
    <span><strong>{n_active:,}</strong> 个活跃天</span>
  </div>
  {h_peak}
</header>

<div class="stats-bar reveal delay-1">
  <div class="stat-cell"><div class="stat-n" data-val="{total_msg}">{total_msg:,}</div><div class="stat-l">总消息数</div></div>
  <div class="stat-cell"><div class="stat-n" data-val="{n_members}">{n_members:,}</div><div class="stat-l">发言成员</div></div>
  <div class="stat-cell"><div class="stat-n" data-val="{n_active}">{n_active:,}</div><div class="stat-l">活跃天数</div></div>
  <div class="stat-cell"><div class="stat-n" data-val="{daily_avg}">{daily_avg:,}</div><div class="stat-l">日均发言次数</div></div>
</div>

<div class="section reveal delay-2">
  <div class="section-head"><span class="section-num">01</span><h2>人名榜单</h2></div>
  <p class="sec-desc">拖动磁贴可重排。首次拖动揭示成员身份。</p>
  {leaderboard_html(charts, C, bg, xiehouyu)}
</div>

<div class="section reveal delay-3" style="padding-bottom:48px">
  <div class="section-head"><span class="section-num">02</span><h2>综合榜 · 人物画像</h2></div>
  <div class="two-col scale-reveal delay-4">
    <div>
      <p class="col-label">综合榜单</p>
      {table_html(portrait_rows, total_msg)}
    </div>
    <div>
      <p class="col-label">人物画像</p>
      {portrait_tabs_html(portrait_rows, messages, C)}
    </div>
  </div>
</div>

<footer>Generated with wechat-group-analytics · huashu.Claude Skill · Powered by manus from Meta (Still)</footer>

<script>{JS}</script>
</body>
</html>"""

    out_path.write_text(html, 'utf-8')
    print(f'Done: {out_path}')


if __name__ == '__main__':
    main()
