"""Merge multiple split chat JSON files into one.

When a group chat exceeds ~100,000 messages, export it in time-range batches
and then merge with this script.

Usage:
    python merge_chat.py chat_part1.json chat_part2.json ... -o chat_merged.json

The input files must follow the chat.json format produced by md_to_json.py
(a list of message objects, or a wrapper object with a "messages" key).

Output preserves all fields, deduplicates by (timestamp, sender, content),
and re-sorts by timestamp ascending.
"""

import argparse
import json
import sys
from pathlib import Path


def load_chat(path: Path) -> tuple[str, list]:
    """Load a chat JSON; return (group_name, messages_list)."""
    data = json.loads(path.read_text(encoding='utf-8'))

    # Support both bare list and wrapper object
    if isinstance(data, list):
        return path.stem, data
    if isinstance(data, dict):
        msgs = data.get('messages') or data.get('records') or []
        group = data.get('group', path.stem)
        return group, msgs

    print(f'[skip] unrecognised format: {path}', flush=True)
    return path.stem, []


def dedup_key(msg: dict) -> tuple:
    """Deduplication key: (timestamp OR ts, sender, first-100-chars of content)."""
    ts = msg.get('timestamp') or msg.get('ts', '')
    sender = msg.get('sender', '')
    content = str(msg.get('content', ''))[:100]
    return (ts, sender, content)


def main():
    parser = argparse.ArgumentParser(
        description='Merge split chat JSON files into one deduplicated file.'
    )
    parser.add_argument('files', nargs='+', help='Input chat JSON files (in chronological order)')
    parser.add_argument('-o', '--output', required=True, help='Output merged JSON file')
    args = parser.parse_args()

    all_msgs = []
    group_name = ''
    seen = set()

    for f in args.files:
        path = Path(f)
        if not path.exists():
            print(f'[skip] not found: {f}', flush=True)
            continue
        gname, msgs = load_chat(path)
        if not group_name:
            group_name = gname
        before = len(all_msgs)
        for msg in msgs:
            k = dedup_key(msg)
            if k not in seen:
                seen.add(k)
                all_msgs.append(msg)
        added = len(all_msgs) - before
        print(f'[loaded] {path.name}: {len(msgs):,} msgs, {added:,} new after dedup', flush=True)

    # Sort by timestamp (supports both int Unix ts and string 'YYYY-MM-DD HH:MM')
    def sort_key(msg):
        ts = msg.get('timestamp') or msg.get('ts', '')
        return str(ts)

    all_msgs.sort(key=sort_key)

    out = {
        'group': group_name,
        'total': len(all_msgs),
        'messages': all_msgs,
    }
    out_path = Path(args.output)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f'[done] {out_path} — {len(all_msgs):,} messages ({size_mb:.1f} MB)', flush=True)


if __name__ == '__main__':
    main()
