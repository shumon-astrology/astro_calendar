# CHANGELOG — SCHEMA_chart

正本は `~/Documents/デジタル販売/10_schema/`。このリポジトリの `schema/` は版数同期した参照コピー。

## v2 rev.1（2026-09-18）— v1 rev.2 からの差分

要件：`10_schema/SCHEMA_v2_要件書_20260918.md` v0.3 第 I 部。
**加算原則**：v1 の全キーは同じ場所・同じ型・同じ意味で残る。既存 enum の変更なし。
機械検証（`tests/test_schema_v2_additive.py`）：
- v2 は `scripts/build_schema_v2.py` の出力と byte 一致（手書きしない）。
- (a) `sample_chart_v1.json` を v2 にかけると、失敗は `schema_version` の const と新設 required 11 件の欠落のみ（計 12 件）。
- (b) v2 から新設キーと nullable 化を外した派生スキーマは、description を除いて v1 と構造一致し、`sample_chart_v1.json` をエラー 0 で通す（GT-6）。

### 1. 版・宣言

| 項目 | v1 rev.2 | v2 rev.1 |
|---|---|---|
| `$id` | `…/chart_v1.json` | `…/chart_v2.json` |
| `schema_version` | const `"v1"` | const `"v2"` |
| `x-schema_file_version` | `v1 (2026-09-17, rev.2: …)` | `v2 (2026-09-18, rev.1)` |
| `x-method` | METHOD v1.2 | METHOD_本質的品位表 v1.2（決定 C は v1.3 待ち）／METHOD_natal_v1 v1.3／古典職業鑑定マニュアル v11＋再基底化差分 |
| `x-requirements` | （なし） | SCHEMA_v2 要件書 v0.3 を追記 |
| `$defs` | （なし） | `planet_name` `house_class` `aspect_contact` `condition` `source_entry` `almuten_keys` `ranking_extreme` を新設 |

### 2. 新設トップレベルブロック（11 個。すべて required）

要件書 v0.3 I-0：プロンプトが「キーの有無」で分岐しないよう、新設ブロックは常に存在させる。

- **非 null**：`derived`、`boundary_warnings`、`summary`、`reading_notes`、`provenance`
- **nullable（該当しないとき null）**：`houses_summary`、`fixed_star_contacts`（v2 rev.1 では null。恒星は保留）、`vocation`、`vocation_blocked_reason`、`timing`（v2 rev.1 では null）、`moon_range`（`time_known:false` のときのみ値を持つ）

### 3. 既存ブロックへの追加キー（すべて任意）

| ブロック | 追加キー |
|---|---|
| `birth_data` | `place` `timezone_id` `time_known` `time_source` `dst_applied`（`tz_offset` は説明のみ補足） |
| `tables_used` | `scoring`（const `"lilly"`）、`ephemeris` `{library, version, frame}`、`timezone` `{source, version}` |
| `tables_used.sources` | `lots` `fixed_stars` `star_catalog` `triplicity_order` `triplicity_audit` `vocation_rules` `derived_thresholds` `planetary_hours`（既存 16 項目と同形） |
| `sect` | `moon_phase_quarter` `season_quarter` `season_quarter_note` |
| `sect.sect_light.triplicity_lords[]` | `rank`（1–3）`role`（day/night/participating）。既存の `order` は互換のため残す |
| `angles.ascendant` / `angles.midheaven` | `also_known_as` `sign_change_within_minutes` `minutes_to_previous_sign` `minutes_to_next_sign` |
| `angles.midheaven` | `lord` と アルムーテン6キー（`almuten` `almuten_tie` `almuten_candidates` `almuten_tie_break` `almuten_scores`）＝ ASC と同形 |
| `houses[]` | アルムーテン6キー（12カスプ。1室＝ASC、10室＝MC と同値） |
| `planets[].essential_dignity` | `peregrine_scored` `peregrine_uncertain` |
| `planets[].accidental_dignity.items[]` | `label_en`（`label_ja` は残す） |
| `nodes.mean[]` / `nodes.true[]` | `also_known_as` |
| `lots.fortune` / `lots.spirit` | `also_known_as` `sect_reversed` `non_reversed_longitude` `non_reversed_position` |
| `aspects[]` | `reception_softens` `reception_minor` `time_unknown_caveat` |

### 4. nullable 化（`time_known: false` 用。oneOf [元の定義, null]）

`sect`／`angles`／`houses`／`lots`／`almuten_figuris`／`houses_summary`／
`planets[].house`・`house_raw`・`near_next_cusp`・`above_horizon`・`accidental_dignity`・`sect`・`total_score`／
`planets[].essential_dignity.peregrine`・`triplicity_rulers.sect_ruler`／
`nodes.mean[].house`・`nodes.true[].house`／`vocation`

`planetary_day_hour` は v1 で既に nullable のため二重化せず、説明のみ補足した（極圏 rev.2 の意味に「出生時刻不明」を追加）。

### 5. 説明の変更（型・意味は不変）

- `planets[].accidental_dignity`：**決定 C**（2026-09-18）を明記。カジミ（≤17′）・燃焼（≤8°30′）・光線下（≤17°）はいずれも太陽と同一サインであることを要し、サインが違えば離角によらず free。典拠は CA I ll.9344–9353（燃焼）。カジミ・光線下への拡張はプロジェクトの決定。**Python・JS の実装変更は Phase 2**。
- `planetary_day_hour`：日出没の定義（視位置・大気差あり 1013.25 hPa／0℃・太陽の円盤中心・海抜 0 m）を明記。詳細は `tables_used.sources.planetary_hours`。
- `tables_used.ephemeris`：Python 側は `"Swiss Ephemeris (Moshier fallback)" 2.10.03`（se1 未配置、Phase 0 で判明）。

### 6. 保留・予約（v2 rev.1 では値を持たない）

- `fixed_star_contacts`：null。56 星カタログは実装せず、キーのみ予約（I-2-1 保留、付録A #16）。v1 の `fixed_stars`（Regulus・Spica・Algol）は現状維持。
- `timing`：null。`vocation.timing_slice`：null（METHOD_timing 未作成）。

## 参照実装（Python）の記録

- **タグ `v1-reference`**：GT-2 の基準となる Python 実装。
  - 2026-09-19 に打ち直した（現在は commit `226e8d6`）。**旧タグは `1f813ff`**（決定 C まで）。
    打ち直しの理由は `prenatal_syzygy.datetime_local` が tz_offset によらず常に JST
    だった不具合の修正（付録 A #19）。値が変わったのは tz≠9 の 8 図の当該キーのみ。
  - 暦は Swiss Ephemeris の Moshier フォールバック（se1 未配置、付録 A #17）。
- **実装候補（保留）**：恒星 Spica は Python が Swiss の内蔵値（視位置）、JS が線形近似で
  約 18″ ずれる。Astronomy Engine の `DefineStar` に ICRS 座標を与えて視位置を計算すれば
  数秒角まで寄せられる見込み。新しい星集合（ロイヤルスター 6＋4〜6）を決めるときに
  併せて検討する（付録 A #16・#21）。

## v1 rev.2（2026-09-17）

- `planetary_day_hour` を `oneOf [object, null]` にし、極圏（白夜・極夜）で日出没が求まらない場合の null を許容。

## v1（2026-09-17）

- 初版。計算機（natal_classical.py）とプロンプトの契約。
