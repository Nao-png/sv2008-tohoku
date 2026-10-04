# 2008年ストリートビュー探索スクリプト

Google ストリートビューの撮影日一覧（タイムマシン）から外れた 2008 年の画像を、
画像どうしのリンクをたどって集めるスクリプトです。Google の非公開 API を
[streetlevel](https://github.com/sk-zk/streetlevel) 経由で使っているため、仕様変更で動かなくなる可能性があります。

## セットアップ

`streetlevel` は依存パッケージ `pyfrpc` のビルドに失敗するため、`--no-deps` で入れて必要なものだけ追加します。

```
python -m venv venv
venv\Scripts\python -m pip install --no-deps streetlevel
venv\Scripts\python -m pip install requests aiohttp numpy pillow pyproj protobuf pycryptodome scipy bd09convertor coordinatesconverter pyexiv2
```

## ファイル

| ファイル | 内容 |
|---|---|
| `ncrawl.py` | 全国版の探索。`panos.csv` に追記し、`frontier.json` から再開できる。引数は同時接続数（例: `32`） |
| `mcrawl.py` | 宮城県版の探索（`miyagi.json` の県境内だけ広げる）。`build_map.py` からも県境の判定に使う |
| `build_map.py` | `panos.csv` から `../index.html` と `../sv2008_panoids.csv` を作る |
| `map_template.html` | 地図の HTML テンプレート（Leaflet + 国土地理院タイル） |
| `probes.json` | 未来へのキオクの「震災前」表示で探した地点と結果（[緯度, 経度, 見つかった画像 ID または null, 調査名]）。地図の「未来へのキオクで検索した地点」に使う |
| `miyagi.json` | 宮城県の県境（OpenStreetMap Nominatim から取得） |
| `panos.csv` | 探索結果の生データ（panoid, 緯度, 経度, 撮影年月）。832,836 行 |
| `probe09*.py`, `yonezawa.py` | 2009 年前半の画像や米沢周辺のつながりを調べた調査用スクリプト |
| `*.log`, `frontier.json` | 探索時のログと、最後に残った未確認キュー（空） |

## 使い方

地図と CSV を作り直す:

```
venv\Scripts\python build_map.py
```

探索をやり直す・続ける場合は `ncrawl.py` を実行します。`panos.csv` に載っている画像は確認済みとして扱い、
`frontier.json` に残っている画像から続きを探します（今回の探索では残りは 0 件で終了しています）。
新しい起点（別地域の 2008 年の画像 ID）から探すときは、`frontier.json` をその ID のリストにして実行してください。
茨城（`b8xXjrWHvgCqbzcMFv6XOA`）と郡山（`ZEs_nnLp4GUMPoTJOR0fxQ`）の起点は、Web Archive に残っていた
「未来へのキオク」の URL（`www.miraikioku.com/?m=sv&...&panoid=...&period=before`）から見つけました。

```
venv\Scripts\python ncrawl.py 32
```
