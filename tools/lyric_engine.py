# -*- coding: utf-8 -*-
"""
歌词引擎（库）：语义切分 + GNU Unifont 点阵取模
==================================================================
被 lrc2data.py 调用，不直接运行。

核心能力：
  split_lyric(line, glossary) —— 把一句歌词按屏宽（128px）切分成 1~3 行，
      断点优先 标点/空格(权重2) > 词边界(权重1)；落在词内部的断点直接排除
      （宁多一行也不切词）；行数最少，再均衡。
  row_bytes(text, glyphs) —— 一行文字 → Adafruit_GFX drawBitmap 格式字节
      （逐行式、MSB 在前、每行按整字节对齐，可放 PROGMEM）。

点阵字库：unifont-18.0.01.hex.gz（本目录），GNU Unifont 16x16，覆盖整个 Unicode，
      繁体/粤语字都有；直接从 .hex 取字形，不经渲染→抗锯齿→阈值，笔画永不消失。
"""
import gzip, itertools, os

GZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unifont-18.0.01.hex.gz")
MAXW = 128
# 断行标记：空格/逗号/连字符（断行时丢弃）；句尾标点如 ? 不在列，保持贴在前词后
SEPARATORS = " ,-"
# 词语表（最长匹配）—— 用来在过长短语内部找"词边界"软断点，避免把双字词切开。
# 已含《红日》《放下》两首歌的常用词；换歌若出现切词，把新歌的词补进这里即可。
GLOSSARY = sorted([
    # 红日
    "顛沛流離", "曲折離奇", "一生之中", "兜兜轉轉", "彎彎曲曲", "徬徨時",
    "紅日之火", "沒趣味", "別流淚", "真的我", "如浪花", "做人",
    "我願", "一生", "永遠", "陪伴", "試過", "獨坐", "一角", "幾多", "落淚",
    "雨夜", "滂沱", "燃點", "閃出", "希冀", "心酸", "捨棄",
    # 放下
    "牵挂", "苦恋", "危楼", "丢架", "喜欢", "火化", "知己", "道理", "分离",
    "幽雅", "遗弃", "却偏", "告诉", "放低", "用尽", "曾学懂", "一首歌", "教我",
    "别再", "种下", "许多", "可惜", "偏偏", "当你", "盛开", "发觉", "不再",
    "昨日", "东西", "却为", "如果", "说过", "很想",
], key=len, reverse=True)


def cw(ch):
    """字符宽度：CJK/全角 16px，其它 8px。"""
    o = ord(ch)
    if 0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF:
        return 16
    return 8


def clean(line):
    """去引号、全角转半角。"""
    for q in ('\u201c', '\u201d', '\u2018', '\u2019', '"', "'"):
        line = line.replace(q, '')
    return line.replace('\uff1f', '?').replace('\uff0c', ',')


def wsum(s):
    return sum(cw(c) for c in s)


def load_hex(path=GZ):
    """读取 Unifont .hex.gz → {codepoint: bytes}。16 宽=32 字节，8 宽=16 字节。"""
    g = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cp_hex, _, data = line.partition(":")
            b = bytes.fromhex(data)
            if len(b) in (32, 16):
                g[int(cp_hex, 16)] = b
    return g


def glossary_spans(line, glossary=GLOSSARY):
    """词表最长匹配，返回每个词的 (start, end) 区间。"""
    spans = []
    i, n = 0, len(line)
    while i < n:
        if line[i] in SEPARATORS:
            i += 1
            continue
        for w in glossary:
            if line.startswith(w, i):
                spans.append((i, i + len(w)))
                i += len(w)
                break
        else:
            i += 1
    return spans


def _best_split(line, cand, total):
    """在候选断点里选 行数最少 → 断点权重和最大 → 最均衡 的最优组合。"""
    lb = (total + MAXW - 1) // MAXW
    for n in range(lb, len(line) + 1):
        best_key, best_idxs = None, None
        for combo in itertools.combinations(cand, n - 1):
            idxs = [0] + [i for i, _ in combo] + [len(line)]
            if any(wsum(line[idxs[k]:idxs[k + 1]]) > MAXW for k in range(n)):
                continue
            weight = sum(w for _, w in combo)
            rag = sum(abs(wsum(line[idxs[k]:idxs[k + 1]]) - total / n) for k in range(n))
            key = (weight, -rag)
            if best_key is None or key > best_key:
                best_key, best_idxs = key, idxs
        if best_idxs is not None:
            return best_idxs
    return None


def split_lyric(line, glossary=GLOSSARY):
    """语义切分：一句 → 1~3 行。"""
    line = clean(line)
    if not line:
        return []
    total = wsum(line)
    if total <= MAXW:
        return [line]

    spans = glossary_spans(line, glossary)
    bounds = {e for _, e in spans}
    cand = []
    for i in range(1, len(line)):
        if line[i - 1] in SEPARATORS or line[i] in SEPARATORS:
            cand.append((i, 2))
        elif i in bounds:
            cand.append((i, 1))
        elif any(s < i < e for s, e in spans):
            continue                        # 落词内部 → 会切词，排除
        else:
            cand.append((i, 0))

    idxs = _best_split(line, cand, total)
    if idxs is None:
        idxs = _best_split(line, [(i, 0) for i in range(1, len(line))], total)

    n = len(idxs) - 1
    segs = [line[idxs[k]:idxs[k + 1]] for k in range(n)]
    out = [s for s in (s.strip(SEPARATORS) for s in segs) if s]
    if len(out) > 3:
        raise SystemExit("一句超过 3 行，超出每页容量: " + line)
    return out


def row_bytes(text, glyphs):
    """一行文字 → (宽px, 字节)，Adafruit_GFX drawBitmap 格式（逐行 MSB 在前）。"""
    data = bytearray()
    for y in range(16):
        for ch in text:
            g = glyphs[ord(ch)]
            data += (g[y * 2:y * 2 + 2] if len(g) == 32 else g[y:y + 1])
    return wsum(text), bytes(data)
