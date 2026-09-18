# traditionalchart-core

古典占星術ネイタル計算のクライアントサイド実装（TypeScript）。
Python の `natal_classical.py`（タグ `v1-reference`）を移植したもの。

- 契約：`../schema/SCHEMA_chart_v2.json`（型は `src/types/chart_v2.d.ts` に自動生成）
- 規則の正本：`~/Documents/デジタル販売/20_method/METHOD_本質的品位表_v1.md`（v1.2＋決定 C）
- 要件：`~/Documents/デジタル販売/10_schema/SCHEMA_v2_要件書_20260918.md`（v0.7）
- 依存：`astronomy-engine`（MIT）のみ。外部通信なし・DOM 非依存

## 現在地（Phase 5）

SCHEMA v2 rev.4 のネイタル側と適職側（`vocation`）を実装済み。`computeChart()` は
`schema_version: "v2"` を書き、戻り値の型は `src/types/chart_v2.d.ts`（スキーマから生成）。

- **参照実装（Python）のタグ：`v1-reference` = `7bc56ff`**（決定 C・決定 D 改まで）。
  GT-2 はこのタグの出力をゴールデンとして比較する。
- **凍結したゴールデン**：較正例 No.001（`test/golden/calibration_No001_vocation.json`、
  2026-09-19 三河監修）。この出力が変われば回帰であり、再監修が要る。

### 未実装（意図的に残しているもの）

| 項目 | 状態 |
|---|---|
| 恒星カタログ（ロイヤルスター 6＋その他 4〜6） | **保留**（付録 A #16）。`fixed_star_contacts` は null、v1 の 3 星のみ使う |
| `timing`（フィルダリア・プロフェクション・トランジット） | **null**。METHOD_timing の作成待ち。`vocation.timing_slice` も null |
| `system_divergence` のプトレマイオス式による全ルール走行 | 未実装（付録 A #38）。候補星の品位と②-B の勝者までを比較し、`significator_ptolemaic` は null |
| Python への v2 実装 | 任意（付録 A #14）。Python は v1 リファレンスとして凍結 |

## 使い方

```bash
npm install
npm test                 # vitest（GT-1 の移植 + GT-2 の差分検証）
npm run typecheck        # tsc --strict
npm run build            # dist/traditionalchart.mjs（単一 ESM）
npm run typegen          # SCHEMA_chart_v2.json から型を再生成

node --experimental-strip-types cli/chart.ts \
  --date 1985-07-21 --time 14:30 --tz Asia/Tokyo --lat 35.6895 --lon 139.6917 --pretty
node --experimental-strip-types cli/chart.ts \
  --date 1985-07-21 --tz Asia/Tokyo --lat 35.6895 --lon 139.6917 --time-unknown

node --experimental-strip-types cli/compare.ts --verbose   # GT-2 の差分表
```

## 構成

```
src/
  util.ts             角度・丸め・位置文字列
  tables.ts           data/*.json の読み込み（表を参照してよい唯一の場所）
  time.ts             現地の壁時計 ↔ ユリウス日
  ephemeris.ts        Astronomy Engine のアダプタ（真黄道 of date・日出没・ノード・朔望）
  houses.ts           ASC／MC／レジオモンタナス 12 カスプ、5°繰り上げ
  dignity.ts          ★共通の品位エンジン（ネイタルも適職もここだけを見る）
  aspects.ts          プトレマイオス 5 種・モイエティ合算・レセプション
  accidental.ts       偶発的品位・太陽光線（決定 C）・ハイズ
  lots.ts             フォーチュン／スピリット・セクト
  timezone.ts         IANA タイムゾーン（Intl の tzdata で壁時計 → UT）
  derived.ts          derived ブロック（I-2）
  serialize.ts        summary テンプレート・reading_notes・provenance
  sources.ts          v2 で新設した出所ラベル
  labels.ts           偶発的品位の英語ラベル
  fixed_stars.ts      恒星 3 星（保留中のため v1 の方式を踏襲）
  planetary_hours.ts  曜日主星・時刻主星
  index.ts            computeChart()
data/                 Python 定数の機械書き出し（scripts/export_tables.py が生成）
test/golden/          Python が生成したゴールデン 10 図（scripts/make_goldens.py）
```

## Python との既知の相違

| 項目 | 内容 |
|---|---|
| 恒星 Spica | Python は Swiss Ephemeris の内蔵値（視位置）、JS は線形近似。約 18″ ずれる（GT-2 では報告のみ） |
| 度分の文字列 | 黄経が 0.02° 以内でも、分の切り捨て境界で 1 分ずれることがある（暦の境界事例） |
| トゥルーノードの逆行フラグ | 停留付近では双方 |速度| < 0.001°/日 で符号が揺れる |

## 天文計算の要点

| 項目 | 方法 |
|---|---|
| 黄経 | `GeoVector(body, t, true)` → `Ecliptic()`（真黄道 of date）。Python と最大 0.0027° |
| 速度 | ±1 時間の差分商 |
| ハウス | 地平線の南北点を通る大円と黄道の交点。上下・東西の別で交点を選ぶ（極圏でも一致） |
| 日出没 | `SearchAltitude()` に高度 **−0.610°** を渡す。Python（視位置・円盤中心・海抜 0 m・1013.25 hPa・0 ℃）と最大 1.6 秒 |
| ノード | 平均＝Meeus 47.7、真＝月の状態ベクトルから瞬時軌道面の昇交点 |
| 朔望 | `SearchMoonPhase(0/180)` を遡って直前の朔望 |
