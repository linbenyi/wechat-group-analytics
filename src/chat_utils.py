"""Shared utilities: stopwords, tokenisation, message type labels."""

import re
from collections import Counter
import jieba

# WeChat built-in emoji names — appear as [名称] in exported chat logs
# Classic set (系统自带)
WECHAT_EMOJI = {
    '微笑','撇嘴','色','发呆','得意','流泪','害羞','闭嘴','睡','大哭',
    '尴尬','发怒','调皮','呲牙','惊讶','难过','酷','冷汗','抓狂','吐',
    '偷笑','愉快','白眼','傲慢','困','惊恐','流汗','憨笑','悠闲','奋斗',
    '咒骂','疑问','嘘','晕','衰','骷髅','敲打','再见','擦汗','抠鼻',
    '鼓掌','坏笑','左哼哼','右哼哼','哈欠','鄙视','委屈','快哭了','阴险',
    '亲亲','可怜','菜刀','西瓜','啤酒','咖啡','猪头','玫瑰','凋谢','嘴唇',
    '爱心','心碎','蛋糕','闪电','炸弹','刀','足球','瓢虫','便便','月亮',
    '太阳','礼物','拥抱','强','弱','握手','胜利','抱拳','勾引','拳头',
    '差劲','爱你','NO','OK',
    # Extended set (扩展表情包 · 第一批)
    '吃瓜','加油','汗','天啊','Emm','社会社会','旺柴','好的','打脸','哇',
    '嘿哈','捂脸',
    # Extended set (扩展表情包 · 第二批)
    '666','裂开','叹气','翻白眼','doge','让我看看','破涕为笑','机智','皱眉',
}

_EMOJI_RE = re.compile(r'\[([^\[\]]+)\]')

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
    """Return the n most common words (jieba + WeChat emoji), stopwords excluded.

    WeChat emoji like [捂脸] are extracted via regex before jieba sees the text,
    so they are counted as single tokens (stored without brackets, e.g. '捂脸').
    """
    words = []
    for t in texts:
        # 1. Extract [emoji] tokens — only known WeChat emoji names count
        for name in _EMOJI_RE.findall(t):
            if name in WECHAT_EMOJI:
                words.append(name)
        # 2. Strip all [...] brackets so jieba doesn't see fragments
        clean = _EMOJI_RE.sub(' ', t)
        # 3. Normal jieba tokenisation on remaining text
        for w in jieba.cut(clean, cut_all=False):
            w = w.strip()
            if len(w) >= 2 and w not in STOPWORDS and not w.isdigit():
                words.append(w)
    return Counter(words).most_common(n)
