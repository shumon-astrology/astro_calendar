#!/usr/bin/env python3
"""
日本全国の市区町村データ（緯度・経度）を生成するスクリプト。

データソース: Geolonia japanese-addresses API (MIT License)
https://github.com/geolonia/japanese-addresses

出力: static/data/japan_cities.json
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

BASE_URL = "https://geolonia.github.io/japanese-addresses/api/ja"


def fetch_json(url):
    """URLからJSONを取得"""
    req = urllib.request.Request(url, headers={"User-Agent": "astro_calendar/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    # 出力先ディレクトリ
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    output_path = os.path.join(project_dir, "static", "data", "japan_cities.json")

    print("=== 日本市区町村座標データ生成 ===")
    print(f"データソース: {BASE_URL}")
    print(f"出力先: {output_path}")
    print()

    # Step 1: 都道府県→市区町村マッピングを取得
    print("都道府県一覧を取得中...")
    pref_cities = fetch_json(f"{BASE_URL}.json")
    total_prefs = len(pref_cities)
    total_cities = sum(len(cities) for cities in pref_cities.values())
    print(f"  {total_prefs} 都道府県, {total_cities} 市区町村")
    print()

    # Step 2: 各市区町村の町名データから平均座標を算出
    result = {}
    processed = 0
    skipped = 0

    for pref_idx, (pref, cities) in enumerate(pref_cities.items(), 1):
        result[pref] = []
        print(f"[{pref_idx}/{total_prefs}] {pref} ({len(cities)} 市区町村)...")

        for city in cities:
            processed += 1
            encoded_city = urllib.parse.quote(city)
            encoded_pref = urllib.parse.quote(pref)
            url = f"{BASE_URL}/{encoded_pref}/{encoded_city}.json"

            try:
                towns = fetch_json(url)
            except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
                print(f"  SKIP: {city} ({e})")
                skipped += 1
                continue

            if not towns:
                print(f"  SKIP: {city} (データなし)")
                skipped += 1
                continue

            # 有効な座標を持つ町名から平均を算出
            lats = [t["lat"] for t in towns if t.get("lat")]
            lngs = [t["lng"] for t in towns if t.get("lng")]

            if lats and lngs:
                avg_lat = round(sum(lats) / len(lats), 4)
                avg_lng = round(sum(lngs) / len(lngs), 4)
                result[pref].append({
                    "name": city,
                    "lat": avg_lat,
                    "lng": avg_lng,
                })
            else:
                print(f"  SKIP: {city} (座標なし)")
                skipped += 1

            # レート制限
            time.sleep(0.05)

        sys.stdout.flush()

    # Step 3: JSON出力
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    # 統計
    total_output = sum(len(v) for v in result.values())
    file_size = os.path.getsize(output_path)
    print()
    print("=== 完了 ===")
    print(f"  都道府県: {len(result)}")
    print(f"  市区町村: {total_output} (スキップ: {skipped})")
    print(f"  ファイルサイズ: {file_size:,} bytes ({file_size/1024:.1f} KB)")
    print(f"  出力: {output_path}")


if __name__ == "__main__":
    main()
