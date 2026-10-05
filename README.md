# lyric_scroller · 歌词滚动器（LRC 时间同步）

[![CI](https://github.com/alphabethoney/lyric_scroller/actions/workflows/ci.yml/badge.svg)](https://github.com/alphabethoney/lyric_scroller/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

一个 **Arduino UNO + 0.96" OLED（128×64）** 的歌词滚动器：输入标准 `.lrc` 文件，
按歌词自带的时间戳逐句滚动，中文用 **GNU Unifont 点阵**（16×16，无抗锯齿、笔画永不消失），
长句自动**语义折行**（不切词），切换带**从屏幕中间向两边展开**的动画。

## 目录结构

```
lyric_scroller/
├── README.md                 本说明
├── build.ps1                 一键构建：生成数据 → 编译 → 烧录
├── lyric_scroller/           Arduino 工程（用 IDE 打开这个文件夹）
│   ├── lyric_scroller.ino    播放器源码
│   └── lyrics.h              由 LRC 生成的数据（自动生成，勿手改）
├── lrc/                      放歌词文件
│   └── fangxia.lrc           示例《放下》
└── tools/                    生成工具（PC 端）
    ├── lrc2data.py           一键：LRC → lyrics.h
    ├── lyric_engine.py       语义切分 + 点阵取模引擎（库）
    └── unifont-18.0.01.hex.gz 点阵字库
```

## 硬件接线

| OLED 引脚 | UNO |
|---|---|
| VCC | 3V3（或 5V，二选一） |
| GND | GND |
| SCL | A5 |
| SDA | A4 |

按键（可选）：**D2 → GND** 暂停/继续，**D3 → GND** 回到开头。

## 跑起来

### 方式一：一键（推荐）

```powershell
.\build.ps1                # 用默认 lrc\fangxia.lrc，自动选端口，生成+编译+烧录
.\build.ps1 -Lrc "lrc\我的歌.lrc"
.\build.ps1 -Port COM6     # 指定串口
.\build.ps1 -NoUpload      # 只生成+编译，不烧录
```

### 方式二：分步

1. **放歌词**：把 `.lrc` 放进 `lrc/`；
2. **生成数据**：`python tools/lrc2data.py "lrc/你的歌词.lrc"`（需要 Python 3 + Pillow）；
3. **编译烧录**：Arduino IDE 打开 `lyric_scroller/lyric_scroller.ino`，板子选 Arduino Uno、
   端口选 COM，上传。需装 `Adafruit_SSD1306`、`Adafruit_GFX` 两个库。

命令行编译（本机路径）：

```powershell
$env:ARDUINO_DIRECTORIES_DATA='E:\Arduino IDE\ArduinoData'
$env:ARDUINO_DIRECTORIES_USER='D:\Desktop\Arduino'
& 'D:\Program Files (x86)\ardiuno\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe' `
    compile --fqbn arduino:avr:uno 'lyric_scroller'
```

## 使用与对齐

- 开机即从 `t=0` 起表，逐句按 LRC 时间戳翻页。
- **与真实音乐对齐**：音乐开始响的那一秒，按一下 **D3**（回到开头、时钟归零），之后全程自动。
- 末句停 `TAIL_MS` 后循环整首（`LOOP=1`）。

## 常用参数（`lyric_scroller.ino` 顶部）

| 宏 | 作用 |
|---|---|
| `TRANSITION` | 0=直接切换(最准时) / 1=中间展开 / 2=溶解渐变 |
| `EXPAND_STEP` | 展开动画每帧向两边扩的像素（越大越快） |
| `TAIL_MS` | 末句额外停留毫秒 |
| `LOOP` | 1=播完循环，0=停在末句 |

## 换歌 / 补词表

1. 换歌：直接放新 `.lrc` → 重跑 `lrc2data.py` → 重烧。
2. 若某句被切开双字词（罕见）：把新歌的词补进 `tools/lyric_engine.py` 的 `GLOSSARY`，
   按长度从长到短排，重跑即可。断点优先级：标点/空格 > 词边界 > 任意字符。

## 从源码构建（clone 后）

仓库**不随带**歌词和点阵字库（原因见「许可」）。clone 后首次构建：

1. 把 `.lrc` 放进 `lrc/`；
2. `.\build.ps1` —— 首次运行会**自动下载** GNU Unifont 字库，再生成、编译、烧录。

## 许可

- 本仓库代码（播放器、生成工具、build.ps1）：**MIT**，见 `LICENSE`；
- 点阵字库 GNU Unifont：**GPL + 字体嵌入例外**，不随仓库分发，构建时自动下载；
- 歌词文件（`.lrc`）：版权归原权利人，不随仓库分发，请自行放入 `lrc/`。

## 说明

- UNO 无音频，本质是"提词器"：滚动节奏由 LRC 时间戳决定，但需要 D3 对齐真实音乐起点。
- 屏幕 0.96" 为 128×64；若用 128×32 屏，改 `SCREEN_H` 为 32 并重排。
