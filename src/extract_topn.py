"""Extract Top-N entries from every chart inside a Plotly HTML report.

Writes a JSON file alongside the HTML with the structure:
  {
    "group": "<folder name>",
    "charts": [
      {"chart": "<title>", "topn": [{"rank":1, "name":"...", "value":...}, ...]},
      ...
    ]
  }

Scatter-type charts emit {"rank", "name", "value_y", "value_x"} instead.

Usage:
    python extract_topn.py <report.html> [report2.html ...] [--n 5]
"""

import base64
import json
import re
import struct
import sys
import argparse
import concurrent.futures
from pathlib import Path


DTYPE_MAP = {
    'i1': ('b', 1), 'u1': ('B', 1),
    'i2': ('<h', 2), 'u2': ('<H', 2),
    'i4': ('<i', 4), 'u4': ('<I', 4),
    'i8': ('<q', 8), 'u8': ('<Q', 8),
    'f4': ('<f', 4), 'f8': ('<d', 8),
}


def decode_typed_array(obj):
    """Decode a Plotly typed-array dict: {"dtype": "f8", "bdata": "<base64>"}."""
    if not isinstance(obj, dict):
        return obj
    dtype = obj.get('dtype')
    bdata = obj.get('bdata')
    if not dtype or not bdata:
        return obj
    info = DTYPE_MAP.get(dtype)
    if not info:
        return obj
    fmt, size = info
    raw = base64.b64decode(bdata)
    count = len(raw) // size
    fmt_str = f'<{count}{fmt[1:]}' if len(fmt) > 1 else fmt * count
    try:
        return list(struct.unpack(fmt_str, raw))
    except Exception:
        return obj


def resolve_array(arr):
    if arr is None:
        return []
    if isinstance(arr, list):
        return arr
    if isinstance(arr, dict):
        decoded = decode_typed_array(arr)
        if isinstance(decoded, list):
            return decoded
    return []


def extract_json_at(s: str, pos: int):
    """Extract a complete JSON object/array starting at pos; return (parsed, end_pos)."""
    opener = s[pos]
    closer = ']' if opener == '[' else '}'
    depth = 0
    in_str = False
    escape = False
    i = pos
    while i < len(s):
        c = s[i]
        if escape:
            escape = False
        elif c == '\\' and in_str:
            escape = True
        elif c == '"':
            in_str = not in_str
        elif not in_str:
            if c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[pos:i + 1]), i + 1
                    except Exception:
                        return None, i + 1
        i += 1
    return None, len(s)


def extract_plots(html: str):
    """Return list of (traces, layout) for every Plotly.newPlot call."""
    plots = []
    pattern = re.compile(r'Plotly\.newPlot\s*\(\s*["\'][^"\']+["\'],\s*')
    for m in pattern.finditer(html):
        pos = m.end()
        if pos >= len(html) or html[pos] != '[':
            continue
        traces, pos = extract_json_at(html, pos)
        if traces is None:
            continue
        while pos < len(html) and html[pos] in ' \t\n\r,':
            pos += 1
        if pos >= len(html) or html[pos] != '{':
            continue
        layout, _ = extract_json_at(html, pos)
        if layout is not None:
            plots.append((traces, layout))
    return plots


def get_title(layout: dict) -> str:
    t = layout.get('title', '')
    if isinstance(t, dict):
        return t.get('text', '')
    return str(t).strip()


def topn_from_traces(traces: list, n: int = 5) -> list:
    """Extract top-n items from the dominant trace in a chart."""
    for trace in traces:
        t = trace.get('type', '')
        orient = trace.get('orientation', '')
        x = resolve_array(trace.get('x'))
        y = resolve_array(trace.get('y'))

        if t == 'bar' and orient == 'h' and x and y:
            pairs = sorted(zip(y, x), key=lambda p: p[1] if isinstance(p[1], (int, float)) else 0, reverse=True)
            return [{'rank': i + 1, 'name': str(nm), 'value': round(v, 1) if isinstance(v, float) else v}
                    for i, (nm, v) in enumerate(pairs[:n])]

        if t == 'bar' and x and y:
            pairs = sorted(zip(x, y), key=lambda p: p[1] if isinstance(p[1], (int, float)) else 0, reverse=True)
            return [{'rank': i + 1, 'name': str(nm), 'value': round(v, 1) if isinstance(v, float) else v}
                    for i, (nm, v) in enumerate(pairs[:n])]

        if t == 'pie':
            labels = resolve_array(trace.get('labels')) or x
            values = resolve_array(trace.get('values')) or y
            pairs = sorted(zip(labels, values), key=lambda p: p[1] if isinstance(p[1], (int, float)) else 0, reverse=True)
            return [{'rank': i + 1, 'name': str(nm), 'value': round(v, 1) if isinstance(v, float) else v}
                    for i, (nm, v) in enumerate(pairs[:n])]

        if t == 'scatter' and x and y:
            text = resolve_array(trace.get('text')) or x
            pairs = sorted(zip(text, y, x), key=lambda p: p[1] if isinstance(p[1], (int, float)) else 0, reverse=True)
            return [{'rank': i + 1, 'name': str(nm), 'value_y': yv, 'value_x': xv}
                    for i, (nm, yv, xv) in enumerate(pairs[:n])]
    return []


def process_html(html_path_str: str, n: int = 5):
    path = Path(html_path_str)
    if not path.exists():
        print(f'[skip] not found: {path}', flush=True)
        return

    group_name = path.parent.name
    print(f'[start] {group_name}', flush=True)
    html = path.read_text(encoding='utf-8')

    plots = extract_plots(html)
    print(f'[parsed] {group_name}: {len(plots)} charts found', flush=True)

    charts = []
    for traces, layout in plots:
        title = get_title(layout)
        if not title or '无数据' in title or '无符合' in title:
            continue
        topn = topn_from_traces(traces, n)
        if topn:
            charts.append({'chart': title, 'topn': topn})

    out = {'group': group_name, 'source': path.name, 'charts': charts}
    out_file = path.parent / f'top{n}.json'
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[done] {group_name} → top{n}.json ({len(charts)} charts)', flush=True)
    return out


def main():
    parser = argparse.ArgumentParser(description='Extract top-N from a Plotly HTML report.')
    parser.add_argument('files', nargs='+', help='Plotly HTML report paths')
    parser.add_argument('--n', type=int, default=5, help='How many top entries to keep (default: 5)')
    args = parser.parse_args()

    if len(args.files) == 1:
        process_html(args.files[0], args.n)
    else:
        print(f'Processing {len(args.files)} files in parallel...', flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(args.files)) as ex:
            list(ex.map(lambda f: process_html(f, args.n), args.files))
        print('All done.', flush=True)


if __name__ == '__main__':
    main()
