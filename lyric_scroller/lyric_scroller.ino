/* ============================================================================
 * 歌词滚动器（LRC 时间同步版）
 * ----------------------------------------------------------------------------
 * 数据：lyrics.h（由 tools/lrc2data.py 从 .lrc 自动生成）：
 *   ROWDATA / ROW_OFF / ROW_W / PAGES —— 歌词行位图（每页 1~3 行，句对齐）
 *   PAGE_TIME[] —— 每页的绝对时间戳（毫秒，来自 LRC 的 [mm:ss.xx]）
 *
 * 播放：开机 t=0 起表，页 k 在 [PAGE_TIME[k], PAGE_TIME[k+1]) 期间显示，
 *       滚动节奏完全由 LRC 时间戳决定（不是固定秒数）。
 *   D2 → GND：暂停/继续（暂停时时钟冻结）
 *   D3 → GND：回到开头（时钟归零）—— 音乐开始响时按一下即可对齐
 *   末页停 TAIL_MS 后循环（LOOP=1 时）。
 *
 * 接线：OLED VCC->3V3(或5V)  GND->GND  SCL->A5  SDA->A4
 * ==========================================================================*/
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "lyrics.h"

#define SCREEN_W 128
#define SCREEN_H 64
#define ROW_H    16
#define ROW_GAP  6

#define TRANSITION 1         // 0 = 直接切换(最准时) 1 = 中间展开 2 = 溶解
#define EXPAND_STEP 4
#define FADE_MS    26
#define MIN_ANIM_MS 600      // 句长小于此值(ms)时跳过动画、瞬时切换，避免跳句
#define TAIL_MS    6000      // 最后一页额外停留多久再循环
#define LOOP       1         // 1 = 播完循环；0 = 停在最后一页

#define BTN_PAUSE   2
#define BTN_RESTART 3

Adafruit_SSD1306 oled(SCREEN_W, SCREEN_H, &Wire, -1);
byte oledAddr = 0;

static const uint8_t BAYER[4][4] PROGMEM = {
  { 0, 8, 2, 10 }, { 12, 4, 14, 6 }, { 3, 11, 1, 9 }, { 15, 7, 13, 5 },
};

byte findOLED() {
  Wire.begin();
  Wire.setWireTimeout(25000, true);
  for (byte a = 0x3C; a <= 0x3D; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) return a;
  }
  return 0;
}

uint8_t pageSlot(uint8_t p, uint8_t k) {
  return pgm_read_byte(&PAGES[(uint16_t)p * 3 + k]);
}
uint8_t pageRowCount(uint8_t p) {
  uint8_t n = 0;
  for (uint8_t k = 0; k < 3; k++) if (pageSlot(p, k) != 0xFF) n++;
  return n;
}
int16_t rowY(uint8_t n, uint8_t k) {
  int16_t total = n * ROW_H + (n - 1) * ROW_GAP;
  return (SCREEN_H - total) / 2 + k * (ROW_H + ROW_GAP);
}

bool rowPixel(uint8_t ridx, int16_t x, int16_t ry) {
  if (ridx == 0xFF) return false;
  uint16_t off = pgm_read_word(&ROW_OFF[ridx]);
  uint8_t w = pgm_read_byte(&ROW_W[ridx]);
  int16_t px = x - (SCREEN_W - (int16_t)w) / 2;
  if (px < 0 || px >= w || ry < 0 || ry >= ROW_H) return false;
  uint8_t bw = (w + 7) / 8;
  uint8_t b = pgm_read_byte(&ROWDATA[off + ry * bw + px / 8]);
  return (b & (0x80 >> (px & 7))) != 0;
}
bool pagePixel(uint8_t p, int16_t x, int16_t y) {
  uint8_t n = pageRowCount(p);
  for (uint8_t k = 0; k < n; k++) {
    int16_t yy = rowY(n, k);
    if (y >= yy && y < yy + ROW_H) return rowPixel(pageSlot(p, k), x, y - yy);
  }
  return false;
}

void drawRow(uint8_t ridx, int16_t y) {
  if (ridx == 0xFF) return;
  uint16_t off = pgm_read_word(&ROW_OFF[ridx]);
  uint8_t w = pgm_read_byte(&ROW_W[ridx]);
  oled.drawBitmap((SCREEN_W - (int16_t)w) / 2, y, &ROWDATA[off], w, ROW_H, SSD1306_WHITE);
}
void renderPage(uint8_t p) {
  oled.clearDisplay();
  uint8_t n = pageRowCount(p);
  for (uint8_t k = 0; k < n; k++) drawRow(pageSlot(p, k), rowY(n, k));
}
void drawPage(uint8_t p) { renderPage(p); oled.display(); }

void maskCols(int left, int right) {
  uint8_t mask[SCREEN_W / 8];
  for (int bx = 0; bx < SCREEN_W / 8; bx++) {
    uint8_t m = 0;
    for (int bit = 0; bit < 8; bit++) {
      int x = bx * 8 + bit;
      if (x >= left && x <= right) m |= 0x80 >> bit;
    }
    mask[bx] = m;
  }
  uint8_t *buf = oled.getBuffer();
  for (int y = 0; y < SCREEN_H; y++) {
    uint8_t *row = buf + y * (SCREEN_W / 8);
    for (int bx = 0; bx < SCREEN_W / 8; bx++) row[bx] &= mask[bx];
  }
}
void expandFromCenter(uint8_t p) {
  int half = SCREEN_W / 2;
  for (int t = 0; t <= half; t += EXPAND_STEP) {
    renderPage(p);
    maskCols(half - t, half + t);
    oled.display();
    delay(FADE_MS);
  }
  drawPage(p);
}
void crossfade(uint8_t pa, uint8_t pb) {
  for (int t = 0; t <= 14; t += 2) {
    uint8_t *buf = oled.getBuffer();
    for (int16_t y = 0; y < SCREEN_H; y++)
      for (int16_t x = 0; x < SCREEN_W; x++) {
        bool a = pagePixel(pa, x, y), b = pagePixel(pb, x, y);
        uint8_t bay = pgm_read_byte(&BAYER[y & 3][x & 3]);
        bool on = (a && b) ? true : (a ? bay > t : (b ? bay <= t : false));
        uint8_t *pbuf = buf + y * (SCREEN_W / 8) + x / 8;
        if (on) *pbuf |= (0x80 >> (x & 7));
        else    *pbuf &= ~(0x80 >> (x & 7));
      }
    oled.display();
    delay(FADE_MS);
  }
  drawPage(pb);
}

void transition(uint8_t prev, uint8_t next) {
#if TRANSITION == 0
  drawPage(next);
#elif TRANSITION == 1
  expandFromCenter(next);
#else
  crossfade(prev, next);
#endif
}

uint8_t findPage(uint32_t elapsed) {
  for (uint8_t k = PAGE_COUNT - 1; k > 0; k--) {
    if (pgm_read_dword(&PAGE_TIME[k]) <= elapsed) return k;
  }
  return 0;
}

// 第 p 句还剩多少毫秒（到下一句）；末句返回一个很大的值
uint32_t pageRemain(uint8_t p) {
  if (p + 1 >= PAGE_COUNT) return 0xFFFFFFFF;
  return pgm_read_dword(&PAGE_TIME[p + 1]) - pgm_read_dword(&PAGE_TIME[p]);
}

uint32_t t0 = 0;
bool paused = false;
uint32_t pauseStart = 0;

void setup() {
  Serial.begin(9600);
  delay(300);
  oledAddr = findOLED();
  if (oledAddr == 0) {
    Serial.println(F("[X] no ACK on 0x3C/0x3D - check wiring"));
    for (;;) { }
  }
  Serial.print(F("[OK] OLED addr = 0x"));
  Serial.println(oledAddr, HEX);
  if (!oled.begin(SSD1306_SWITCHCAPVCC, oledAddr)) {
    Serial.println(F("[X] oled.begin failed"));
    for (;;) { }
  }
  Wire.setClock(400000L);
  pinMode(BTN_PAUSE, INPUT_PULLUP);
  pinMode(BTN_RESTART, INPUT_PULLUP);
  t0 = millis();
  Serial.print(F("[OK] lyric scroller: "));
  Serial.print(PAGE_COUNT);
  Serial.print(F(" pages, "));
  Serial.print(ROW_COUNT);
  Serial.println(F(" rows"));
  Serial.println(F("[i] D2=pause  D3=restart"));
}

void loop() {
  static bool lastPause = HIGH, lastRestart = HIGH, first = true;
  static uint8_t cur = 0;

  bool b = digitalRead(BTN_PAUSE);
  if (b == LOW && lastPause == HIGH) {
    if (!paused) { paused = true; pauseStart = millis(); }
    else { paused = false; t0 += millis() - pauseStart; }
    Serial.println(paused ? F("[i] PAUSED") : F("[i] RESUME"));
    delay(150);
  }
  lastPause = b;

  bool r = digitalRead(BTN_RESTART);
  if (r == LOW && lastRestart == HIGH) {
    t0 = millis(); paused = false; cur = 0; first = true;
    drawPage(0);
    Serial.println(F("[i] RESTART"));
    delay(150);
  }
  lastRestart = r;

  if (paused) return;

  uint32_t elapsed = millis() - t0;

#if LOOP
  uint32_t end = pgm_read_dword(&PAGE_TIME[PAGE_COUNT - 1]) + TAIL_MS;
  if (elapsed >= end) { t0 = millis(); elapsed = 0; cur = 0; first = true; }
#endif

  uint8_t page = findPage(elapsed);
  if (page != cur || first) {
    if (first) drawPage(page);
    else if (pageRemain(page) < MIN_ANIM_MS) drawPage(page);   // 太密：瞬时切换
    else transition(cur, page);
    first = false;
    cur = page;
    Serial.print(F("[i] page "));
    Serial.print(page + 1);
    Serial.print(F("/"));
    Serial.print(PAGE_COUNT);
    Serial.print(F(" @"));
    Serial.print(elapsed / 1000);
    Serial.println(F("s"));
  }
}
