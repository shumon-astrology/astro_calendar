"""
占星術カレンダー Webアプリ
Flask wrapper for astro_calendar.py

使い方（ローカル）:
    python3 app.py
    → http://127.0.0.1:5000/ をブラウザで開く
"""

from flask import Flask, render_template, request, jsonify, Response
import astro_calendar as ac
import natal
import io
import contextlib
import os

app = Flask(__name__)


@app.route("/")
def index():
    """メインページを表示"""
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """年月を受け取り、両ファイルの内容をJSONで返す"""
    try:
        year = int(request.form.get("year", 0))
        month = int(request.form.get("month", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "年と月を正しく入力してください"}), 400

    if not (1900 <= year <= 2100):
        return jsonify({"error": "年は1900〜2100の範囲で指定してください"}), 400
    if not (1 <= month <= 12):
        return jsonify({"error": "月は1〜12の範囲で指定してください"}), 400

    # generate関数のprint出力を抑制
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        file1 = ac.generate_file1(year, month)
        file2 = ac.generate_file2(year, month)

    return jsonify({
        "file1": file1,
        "file2": file2,
        "file1_name": f"moon_voc_{year}_{month:02d}.txt",
        "file2_name": f"planet_aspects_{year}_{month:02d}.txt",
    })


@app.route("/download/<file_type>/<int:year>/<int:month>")
def download(file_type, year, month):
    """テキストファイルとしてダウンロード"""
    if not (1900 <= year <= 2100) or not (1 <= month <= 12):
        return "パラメータが不正です", 400

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        if file_type == "file1":
            content = ac.generate_file1(year, month)
            filename = f"moon_voc_{year}_{month:02d}.txt"
        elif file_type == "file2":
            content = ac.generate_file2(year, month)
            filename = f"planet_aspects_{year}_{month:02d}.txt"
        else:
            return "不正なファイルタイプです", 400

    return Response(
        content,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/natal")
def natal_page():
    """ネイタルチャート＆トランジットページを表示"""
    return render_template("natal.html")


@app.route("/natal/calculate", methods=["POST"])
def natal_calculate():
    """出生データからネイタルチャートとトランジットを計算"""
    try:
        birth_year = int(request.form.get("birth_year", 0))
        birth_month = int(request.form.get("birth_month", 0))
        birth_day = int(request.form.get("birth_day", 0))
        birth_hour = int(request.form.get("birth_hour", 0))
        birth_minute = int(request.form.get("birth_minute", 0))
        lat = float(request.form.get("lat", 0))
        lon = float(request.form.get("lon", 0))
        tz_offset = float(request.form.get("tz_offset", 9.0))
        transit_year = int(request.form.get("transit_year", 0))
        transit_month = int(request.form.get("transit_month", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "入力値が不正です"}), 400

    if not (1900 <= birth_year <= 2100):
        return jsonify({"error": "出生年は1900〜2100の範囲で指定してください"}), 400
    if not (1 <= birth_month <= 12) or not (1 <= birth_day <= 31):
        return jsonify({"error": "出生日を正しく入力してください"}), 400
    if not (0 <= birth_hour <= 23) or not (0 <= birth_minute <= 59):
        return jsonify({"error": "出生時刻を正しく入力してください"}), 400
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return jsonify({"error": "緯度・経度を正しく入力してください"}), 400
    if not (-12 <= tz_offset <= 14):
        return jsonify({"error": "タイムゾーンを正しく入力してください"}), 400
    if not (1900 <= transit_year <= 2100) or not (1 <= transit_month <= 12):
        return jsonify({"error": "トランジット月を正しく入力してください"}), 400

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        natal_chart = natal.calculate_natal_chart(
            birth_year, birth_month, birth_day,
            birth_hour, birth_minute, lat, lon, tz_offset
        )
        transits = natal.find_transits_to_natal(
            natal_chart, transit_year, transit_month
        )

    birth_info = {
        "year": birth_year, "month": birth_month, "day": birth_day,
        "hour": birth_hour, "minute": birth_minute,
        "lat": lat, "lon": lon,
    }

    natal_text = natal.generate_natal_text(natal_chart, birth_info)
    transit_text = natal.generate_transit_text(
        natal_chart, transits, transit_year, transit_month, birth_info
    )

    # JSON用にシリアライズ（jdフィールドは不要）
    transits_json = []
    for t in transits:
        t_copy = {k: v for k, v in t.items() if k != "jd"}
        transits_json.append(t_copy)

    return jsonify({
        "natal": natal_chart,
        "transits": transits_json,
        "natal_text": natal_text,
        "transit_text": transit_text,
    })


@app.route("/natal/download", methods=["POST"])
def natal_download():
    """ネイタル＋トランジットレポートをテキストファイルとしてダウンロード"""
    try:
        birth_year = int(request.form.get("birth_year", 0))
        birth_month = int(request.form.get("birth_month", 0))
        birth_day = int(request.form.get("birth_day", 0))
        birth_hour = int(request.form.get("birth_hour", 0))
        birth_minute = int(request.form.get("birth_minute", 0))
        lat = float(request.form.get("lat", 0))
        lon = float(request.form.get("lon", 0))
        tz_offset = float(request.form.get("tz_offset", 9.0))
        transit_year = int(request.form.get("transit_year", 0))
        transit_month = int(request.form.get("transit_month", 0))
    except (ValueError, TypeError):
        return "パラメータが不正です", 400

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        natal_chart = natal.calculate_natal_chart(
            birth_year, birth_month, birth_day,
            birth_hour, birth_minute, lat, lon, tz_offset
        )
        transits = natal.find_transits_to_natal(
            natal_chart, transit_year, transit_month
        )

    birth_info = {
        "year": birth_year, "month": birth_month, "day": birth_day,
        "hour": birth_hour, "minute": birth_minute,
        "lat": lat, "lon": lon,
    }

    content = natal.generate_natal_text(natal_chart, birth_info)
    content += "\n\n"
    content += natal.generate_transit_text(
        natal_chart, transits, transit_year, transit_month, birth_info
    )

    filename = (f"natal_transit_{birth_year}{birth_month:02d}{birth_day:02d}"
                f"_{transit_year}{transit_month:02d}.txt")

    return Response(
        content,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="127.0.0.1", port=port)
