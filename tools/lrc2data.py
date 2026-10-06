# -*- coding: utf-8 -*-
"""
LRC → 点阵歌词数据（一键工具）
==================================================================
用法：  python tools/lrc2data.py <lrc文件>
输出：  lyric_scroller/lyrics.h（含 ROWDATA/ROW_OFF/ROW_W/PAGES + PAGE_TIME 时间轴）

支持：  [mm:ss.xx]、[mm:ss:xx]、[mm:ss] 三种时间格式；[ti:][ar:][offset:] 元数据。
        自动过滤片头制作名单（含全角冒号「：」的行）和"下载歌词"宣传语。
"""
import importlib.util, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKETCH_DIR = os.path.join(ROOT, "lyric_scroller")

import lyric_engine as eng

TS_RE = re.compile(r'\[(\d+):(\d+)(?:[.:](\d+))?\]')
META_RE = re.compile(r'\[(ti|ar|al|by|re|ve|offset):([^\]]*)\]')
SKIP_MARKERS = ("：", "下载歌词")


def _read_lrc_text(path):
    """读文件并自动识别编码：优先 UTF-8，失败回退 GBK。"""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")   # 兜底，避免崩溃


def parse_lrc(path):
    """解析 .lrc → [(ms, 歌词文本)]，按时间排序，应用 offset。"""
    entries, offset = [], 0
    for line in _read_lrc_text(path).splitlines():
        line = line.strip()
        if not line:
            continue
        m = META_RE.match(line)
        if m:
            if m.group(1).lower() == "offset":
                try:
                    offset = int(m.group(2).strip())
                except ValueError:
                    pass
            continue
        times = TS_RE.findall(line)
        if not times:
            continue
        text = TS_RE.sub("", line).strip()
        if not text or any(k in text for k in SKIP_MARKERS):
            continue
        h, mm, frac = times[0]
        ms = int(h) * 60000 + int(mm) * 1000
        if frac:
            ms += int(frac) * (100 if len(frac) == 1 else 10 if len(frac) == 2 else 1)
        entries.append((ms, text))
    entries.sort()
    return [(max(0, ms + offset), t) for ms, t in entries]


def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法: python tools/lrc2data.py <lrc文件>")
    lrc = sys.argv[1]
    if not os.path.isfile(lrc):
        raise SystemExit("找不到文件: " + lrc)

    glyphs = eng.load_hex()
    entries = parse_lrc(lrc)
    if not entries:
        raise SystemExit("LRC 里没解析到任何带时间戳的歌词行")

    pages = [(ms, eng.split_lyric(text)) for ms, text in entries]   # 每句一页

    seen, unique, ub = {}, [], []
    def idx(r):
        if r not in seen:
            seen[r] = len(unique)
            unique.append(r)
            ub.append(eng.row_bytes(r, glyphs))
        return seen[r]

    page_idx, page_time = [], []
    for ms, rows in pages:
        t = [idx(rows[0])]
        t.append(idx(rows[1]) if len(rows) >= 2 else 255)
        t.append(idx(rows[2]) if len(rows) >= 3 else 255)
        page_idx.append(t)
        page_time.append(ms)

    offsets, roww, rowdata = [], [], bytearray()
    for w, b in ub:
        offsets.append(len(rowdata))
        roww.append(w)
        rowdata += b

    print(f"LRC: {os.path.basename(lrc)}")
    print(f"歌词 {len(entries)} 句 → {len(page_idx)} 页（去重 {len(unique)} 行）")
    print(f"时长 {page_time[-1]/1000:.1f}s，位图 {len(rowdata)} 字节")

    os.makedirs(SKETCH_DIR, exist_ok=True)
    hp = os.path.join(SKETCH_DIR, "lyrics.h")
    with open(hp, "w", encoding="utf-8") as f:
        f.write("// 由 tools/lrc2data.py 自动生成，请勿手改\n")
        f.write("// 来源: " + os.path.basename(lrc) + "\n")
        f.write("// 字体: GNU Unifont 18.0.01（16x16 点阵）\n\n")
        f.write(f"#define ROW_COUNT {len(unique)}\n")
        f.write(f"#define PAGE_COUNT {len(page_idx)}\n\n")
        f.write("static const unsigned char ROWDATA[] PROGMEM = {\n")
        for i in range(0, len(rowdata), 12):
            f.write("  " + ", ".join(f"0x{b:02X}" for b in rowdata[i:i + 12]) + ",\n")
        f.write("};\n\n")
        f.write("static const uint16_t ROW_OFF[ROW_COUNT] PROGMEM = {" +
                ", ".join(str(o) for o in offsets) + "};\n")
        f.write("static const uint8_t ROW_W[ROW_COUNT] PROGMEM = {" +
                ", ".join(str(w) for w in roww) + "};\n")
        f.write("static const uint8_t PAGES[PAGE_COUNT * 3] PROGMEM = {" +
                ", ".join(str(x) for p in page_idx for x in p) + "};\n")
        f.write("static const uint32_t PAGE_TIME[PAGE_COUNT] PROGMEM = {" +
                ", ".join(str(t) for t in page_time) + "};\n")
    print("已写: " + hp)


if __name__ == "__main__":
    main()
