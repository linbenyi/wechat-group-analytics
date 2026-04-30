"""Shared utilities: stopwords, tokenisation, message type labels."""

from collections import Counter
import jieba

STOPWORDS = set("""
的 了 是 我 你 他 她 它 们 这 那 有 在 不 也 都 就 和 与 但 或
啊 哈 嗯 呢 吧 呀 哦 哇 嘛 哎 么 哟 唉 嗨 诶 噢 哈哈 哈哈哈 嗯嗯
一个 什么 怎么 这个 那个 一下 可以 没有 一样 因为 所以 还是 已经
然后 还有 就是 这样 那样 如果 虽然 但是 不是 觉得 感觉 知道 现在
大家 自己 我们 你们 他们 时候 地方 东西 事情 问题 应该 需要 可能
好的 好啊 对的 对啊 哦哦 啊啊 来 去 说 做 看 想 用 会 让 给
从 到 把 被 为 对 上 下 里 外 前 后 中 没 很 太 都 才 真的 一直
图片 链接 文件 表情 视频 通话 小程序 系统 回复 local_id 所有人
""".split())

MSG_TYPE_LABELS = {
    'text': '文本', 'image': '图片', 'sticker': '表情',
    'link': '链接', 'file': '文件', 'video': '视频',
    'voice': '语音', 'call': '通话', 'reply': '回复',
    'system': '系统', 'location': '位置',
}


def top_words(texts, n=30):
    """Return the n most common jieba-tokenised words, stopwords excluded."""
    words = []
    for t in texts:
        for w in jieba.cut(t, cut_all=False):
            w = w.strip()
            if len(w) >= 2 and w not in STOPWORDS and not w.isdigit():
                words.append(w)
    return Counter(words).most_common(n)
