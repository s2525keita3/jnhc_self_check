"""動作確認用のデモデータ（架空）を data/demo/ に生成する。

実在の事業所とは一切関係ない。名称はすべて「デモ」で始まり、
ダッシュボードにもデモである旨の帯が出る。
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent / "data" / "demo"
rng = random.Random(42)

WARDS = {  # 区ごとのざっくりした範囲（lat, lon）
    "緑区": ((35.56, 35.62), (139.22, 139.34)),
    "中央区": ((35.56, 35.60), (139.34, 139.40)),
    "南区": ((35.51, 35.56), (139.38, 139.44)),
}
WARD_W = {"緑区": 0.25, "中央区": 0.4, "南区": 0.35}
CORPS = [("株式会社", 0.55), ("合同会社", 0.1), ("医療法人社団", 0.15), ("社会福祉法人", 0.08),
         ("一般社団法人", 0.07), ("特定非営利活動法人", 0.05)]


def pick(weights):
    r, acc = rng.random(), 0.0
    for k, w in weights:
        acc += w
        if r <= acc:
            return k
    return weights[-1][0]


def place(ward):
    (a, b), (c, d) = WARDS[ward]
    return round(rng.uniform(a, b), 5), round(rng.uniform(c, d), 5)


def wareki(ts: pd.Timestamp) -> str:
    if ts >= pd.Timestamp("2019-05-01"):
        return f"R{ts.year - 2018:>2}.{ts.month:>2}.{ts.day:>2}"
    return f"H{ts.year - 1988:>2}.{ts.month:>2}.{ts.day:>2}"


def make_stations(n=90):
    rows = []
    for i in range(n):
        ward = pick(list(WARD_W.items()))
        corp_form = pick(CORPS)
        # 開設年は近年ほど多い
        year = min(2026, int(2004 + 22 * (rng.random() ** 0.6)))
        start = pd.Timestamp(year, rng.randint(1, 12), 1)
        fte = max(2.5, rng.lognormvariate(1.6, 0.45))
        # 廃止ハザード: 開設初期・小規模・営利ほど高い（デモ用の仮定）
        base = 0.06 * (1.8 if fte < 5 else 0.8) * (1.3 if corp_form in ("株式会社", "合同会社") else 0.8)
        life = 0.0
        while True:
            h = base * (2.0 if life < 3 else 1.0)
            if rng.random() < h:
                break
            life += 1
            if life > 40:
                break
        end = start + pd.DateOffset(months=int(life * 12 + rng.randint(1, 11)))
        lat, lon = place(ward)
        rows.append(dict(code=f"{9900000 + i}", name=f"デモ訪問看護ステーション{chr(65 + i % 26)}{i:02d}",
                         ward=ward, corp=f"{corp_form}デモ{i:02d}", start=start, end=end, lat=lat, lon=lon, fte=fte))
    return rows


def main():
    for sub in ("kouseikyoku_houkan", "kaigo_opendata", "iryou_opendata", "shougai_opendata"):
        (ROOT / sub).mkdir(parents=True, exist_ok=True)
    (ROOT / "DEMO").write_text("デモデータ", encoding="utf-8")
    stations = make_stations()

    # 厚生局名簿の月次スナップショット 2019-01〜2026-08
    months = pd.date_range("2019-01-01", "2026-08-01", freq="MS")
    for m in months:
        live = [s for s in stations if s["start"] <= m < s["end"]]
        df = pd.DataFrame([{
            "項番": k + 1, "ステーションコード": s["code"], "事業所名称": s["name"],
            "事業所所在地": f"神奈川県相模原市{s['ward']}デモ町{k + 1}-1", "電話番号": "042-000-0000",
            "開設者名": s["corp"], "指定年月日": wareki(s["start"]),
        } for k, s in enumerate(live)])
        path = ROOT / "kouseikyoku_houkan" / f"{m:%Y%m}_houmonkango_kanagawa"
        if m == months[-1]:  # 最新月はExcel（表題行つき）で読込テストも兼ねる
            with pd.ExcelWriter(path.with_suffix(".xlsx")) as w:
                pd.DataFrame([["コード内容別医療機関一覧表（訪問看護）"], [f"令和{m.year - 2018}年{m.month}月1日現在"], []]) \
                    .to_excel(w, header=False, index=False)
                df.to_excel(w, startrow=4, index=False)
        else:
            df.to_csv(path.with_suffix(".csv"), index=False, encoding="cp932")

    # 介護公表オープンデータ（最新）: 訪問看護・居宅・包括
    last = months[-1]
    rows = []
    for s in stations:
        if s["start"] <= last < s["end"]:
            rows.append({"事業所番号": s["code"], "事業所名": s["name"], "サービスの種類": "訪問看護",
                         "住所": f"神奈川県相模原市{s['ward']}デモ町", "緯度": s["lat"], "経度": s["lon"],
                         "法人の名称": s["corp"], "事業開始年月日": s["start"].strftime("%Y-%m-%d")})
    for i in range(110):
        w = pick(list(WARD_W.items()))
        lat, lon = place(w)
        rows.append({"事業所番号": f"98{i:05d}", "事業所名": f"デモ居宅介護支援事業所{i:03d}",
                     "サービスの種類": "居宅介護支援", "住所": f"神奈川県相模原市{w}デモ町",
                     "緯度": lat, "経度": lon, "法人の名称": f"{pick(CORPS)}デモ居宅{i:03d}"})
    for i in range(29):
        w = pick(list(WARD_W.items()))
        lat, lon = place(w)
        rows.append({"事業所番号": f"97{i:05d}", "事業所名": f"デモ高齢者支援センター{i:02d}",
                     "サービスの種類": "地域包括支援センター", "住所": f"神奈川県相模原市{w}デモ町",
                     "緯度": lat, "経度": lon, "法人の名称": f"社会福祉法人デモ{i:02d}"})
    # 対象外地域の行（フィルタのテスト）
    rows.append({"事業所番号": "0000001", "事業所名": "デモ町田訪問看護", "サービスの種類": "訪問看護",
                 "住所": "東京都町田市デモ町", "緯度": 35.54, "経度": 139.44, "法人の名称": "株式会社デモ"})
    pd.DataFrame(rows).to_csv(ROOT / "kaigo_opendata" / f"{last:%Y%m}_jigyosho_demo.csv",
                              index=False, encoding="utf-8-sig")

    # 医療情報ネット（病院・診療所）
    med = []
    for i in range(24):
        w = pick(list(WARD_W.items()))
        lat, lon = place(w)
        med.append({"ID": f"H{i:04d}", "正式名称": f"デモ病院{i:02d}", "施設種別": "病院",
                    "所在地": f"神奈川県相模原市{w}デモ町", "緯度": lat, "経度": lon,
                    "病床数合計": rng.choice([60, 99, 120, 199, 300, 450, 600])})
    for i in range(60):
        w = pick(list(WARD_W.items()))
        lat, lon = place(w)
        med.append({"ID": f"C{i:04d}", "正式名称": f"デモクリニック{i:02d}", "施設種別": "診療所",
                    "所在地": f"神奈川県相模原市{w}デモ町", "緯度": lat, "経度": lon, "病床数合計": 0})
    med = pd.DataFrame(med).rename(columns={"施設種別": "種別"})
    med.to_csv(ROOT / "iryou_opendata" / f"{last:%Y%m}_facility_demo.csv", index=False, encoding="utf-8-sig")

    # 障害福祉 相談支援
    sd = []
    for i in range(40):
        w = pick(list(WARD_W.items()))
        lat, lon = place(w)
        sd.append({"事業所番号": f"96{i:05d}", "事業所の名称": f"デモ相談支援センター{i:02d}",
                   "サービス種別": "計画相談支援", "事業所住所": f"神奈川県相模原市{w}デモ町",
                   "緯度": lat, "経度": lon, "法人の名称": f"特定非営利活動法人デモ相談{i:02d}"})
    pd.DataFrame(sd).to_csv(ROOT / "shougai_opendata" / f"{last:%Y%m}_soudan_demo.csv",
                            index=False, encoding="utf-8-sig")

    # 人員表（公表システム詳細＋ヒアリングを想定）
    st = []
    for s in stations:
        if not (s["start"] <= last < s["end"]):
            continue
        full = max(1, round(s["fte"] * 0.7))
        part = max(0, round((s["fte"] - full) / 0.5))
        total = full + part
        young = rng.random() < 0.5 if s["start"].year >= 2020 else rng.random() < 0.25
        exp = [rng.randint(0, 2) + (1 if young else 0), rng.randint(0, 3), rng.randint(0, 2), 0, 0]
        rest = max(0, total - sum(exp))
        exp[3] = rest // 2
        exp[4] = rest - exp[3]
        row = {"事業所番号": s["code"], "事業所名": s["name"],
               "看護職員_常勤": full, "看護職員_非常勤": part, "看護職員_常勤換算": round(s["fte"], 1),
               "リハ職_常勤": rng.randint(0, 3), "リハ職_非常勤": rng.randint(0, 2),
               "経験_1年未満": exp[0], "経験_1-3年": exp[1], "経験_3-5年": exp[2],
               "経験_5-10年": exp[3], "経験_10年以上": exp[4],
               "前年度_採用者数": rng.randint(0, 3), "前年度_退職者数": rng.randint(0, 3 if young else 2),
               "調査日": f"{last:%Y-%m-%d}", "出典": "デモ"}
        if rng.random() < 0.6:  # 年代はヒアリングできた分だけ
            ages = [0] * 5
            for _ in range(total):
                ages[min(4, max(0, int(rng.gauss(1.3 if young else 2.2, 1.0))))] += 1
            row.update(dict(zip(["年代_20代", "年代_30代", "年代_40代", "年代_50代", "年代_60代以上"], ages)))
        st.append(row)
    pd.DataFrame(st).to_csv(ROOT / "staff.csv", index=False, encoding="utf-8-sig")
    print(f"デモデータを {ROOT} に生成（ステーション{len(stations)}件・月次名簿{len(months)}本）")


if __name__ == "__main__":
    main()
