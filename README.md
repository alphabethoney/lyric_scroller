# lyric_scroller

基于 **Arduino UNO** 与 **0.96" OLED（SSD1306，128×64）** 的 LRC 歌词滚动器：读取标准 `.lrc` 文件，按其中时间戳逐句同步显示，适用于卡拉 OK 提词、桌面歌词屏等场景。

[![CI](https://github.com/alphabethoney/lyric_scroller/actions/workflows/ci.yml/badge.svg)](https://github.com/alphabethoney/lyric_scroller/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 特性

- **时间戳精确同步**：以 `millis()` 晶振时钟 + 绝对时间戳查表驱动，无累积漂移；
- **点阵渲染**：中文使用 GNU Unifont 16×16 位图，覆盖全部 CJK（含繁体），无乱码、无笔画缺失；
- **语义折行**：长句自动折行，优先标点/空格、其次词边界，不切词；
- **切换动画**：直接 / 从屏幕中线向两侧展开 / 溶解，三种可选；
- **编码兼容**：生成工具自动识别 UTF-8 与 GBK 编码的歌词文件；
- **交互**：暂停 / 继续、回到开头、循环播放。

## 硬件

| OLED | Arduino UNO |
|---|---|
| VCC | 3V3（或 5V，二选一） |
| GND | GND |
| SCL | A5 |
| SDA | A4 |

按键（可选，内置上拉）：**D2 → GND** 暂停 / 继续；**D3 → GND** 回到开头并归零。

## 依赖

- 硬件：Arduino UNO、SSD1306 0.96" OLED（I2C）
- Arduino 库：`Adafruit_SSD1306`、`Adafruit_GFX`
- 构建工具：Python 3（生成数据）、arduino-cli（命令行构建，可选）

## 快速开始

### 一键构建（PowerShell）

```powershell
.\build.ps1                          # 默认 lrc\fangxia.lrc，自动选择端口
.\build.ps1 -Lrc "lrc\你的歌词.lrc"  # 指定歌词文件
.\build.ps1 -Port COM6               # 指定串口
.\build.ps1 -NoUpload                # 只生成数据 + 编译，不烧录
```

`build.ps1` 自动完成：检查字库（缺失时下载）→ 生成 `lyrics.h` → 编译 → 烧录。

### 手动

1. 将 `.lrc` 文件放入 `lrc/`；
2. 生成数据：`python tools/lrc2data.py "lrc/你的歌词.lrc"`；
3. 用 Arduino IDE 打开 `lyric_scroller/lyric_scroller.ino`，选择 Arduino Uno 后上传。

## 使用

1. 上电后即从 `t=0` 起表；
2. 在音乐开始响的瞬间按 **D3**，使时间归零与音乐对齐，之后全程自动翻页；
3. **D2** 随时暂停 / 继续；播放到末句停留 `TAIL_MS` 后循环（`LOOP=1`）。

## 配置

`lyric_scroller/lyric_scroller.ino` 顶部的宏：

| 宏 | 默认值 | 说明 |
|---|---|---|
| `TRANSITION` | 1 | 0=直接切换 1=中间展开 2=溶解渐变 |
| `EXPAND_STEP` | 4 | 展开动画每帧扩展像素 |
| `FADE_MS` | 26 | 动画每帧延时（ms） |
| `MIN_ANIM_MS` | 600 | 句长小于该值时跳过动画、瞬时切换 |
| `TAIL_MS` | 6000 | 末句额外停留（ms） |
| `LOOP` | 1 | 1=循环播放 0=停在末句 |
| `BTN_PAUSE` / `BTN_RESTART` | 2 / 3 | 暂停 / 归零按键引脚 |

## 目录结构

```
lyric_scroller/
├── lyric_scroller/
│   ├── lyric_scroller.ino    播放器源码
│   └── lyrics.h              由 LRC 生成的数据（勿手改）
├── lrc/
│   └── fangxia.lrc           示例歌词
├── tools/
│   ├── lrc2data.py           LRC → lyrics.h
│   ├── lyric_engine.py       语义折行 + 点阵取模
│   └── unifont-18.0.01.hex.gz  点阵字库
├── build.ps1                 一键构建
└── README.md
```

## 词表维护

若个别长句被切分在词语内部，可将该词加入 `tools/lyric_engine.py` 的 `GLOSSARY`（按长度降序排列），重新生成数据即可。

## 许可

- 代码：**MIT**，见 `LICENSE`；
- 点阵字库：**GNU Unifont，GPL + 字体嵌入例外**，见 `tools/UNIFONT-LICENSE.md`；
- 示例歌词：版权归原权利人所有，仅作演示。

## 已知限制

- Arduino UNO 无音频输出，本项目为**时间同步的歌词提示器**，需配合外部音源；
- 默认适配 128×64 屏幕；128×32 屏需修改 `SCREEN_H` 并重新布局。
