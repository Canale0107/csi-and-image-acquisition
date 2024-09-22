# Image Acquisition

## 概要
カメラ（複数台対応）からの画像を保存すると同時に、画像のメタデータ（セッションID、カメラのインデックス、画像のパス、タイムスタンプ）をCSV、InfluxDBに記録する。
- セッションID：データ取得セッションを表すIDで、`session_%Y%m%d-%H%M%S`(JST)で表される。
- カメラのインデックス：opencvでカメラを指定するのに用いるインデックス。`check_camera.py`で確認できる。
- 画像のパス：以下に示す構造で保存される画像のパス
- タイムスタンプ：日時(UTC)のタイムスタンプ

## ファイル構成

```
image-acquisition/
│
├── image_acquisition/
│   ├── camera/
│   │   ├── camera.py               # カメラの管理（Cameraクラス、CameraManagerクラス）
│   │   ├── meta_camera.py          # メタデータ付与機能付きカメラの管理（MetaCameraクラス、MetaCameraManagerクラス）
│   │   └── meta_frame.py           # メタデータ付き画像の定義（MetaDataクラス、MetaFrameクラス）
│   │
│   ├── main/
│   │   ├── acquirer_manager.py     # データ取得管理（ImageAcquirerクラス、ImageAcquirerManagerクラス）
│   │   └── runner_manager.py       # データ取得実行クラス (Runnerクラス、RunnerManagerクラス)
│   │
│   ├── writers/
│   │   ├── abstract_writer.py      # 抽象クラス（DataWriter, WriterManagerの抽象クラス）
│   │   ├── csv_writer.py           # CSVWriter, CSVWriterManagerクラス
│   │   └── db_writer.py            # InfluxDBWriter, InfluxDBWriterManagerクラス
│   │
│   ├── config/
│   │   └── config_loader.py        # 設定ファイルの読み込み（load_configs関数）
│   │
│   ├── logger/
│   │   └── setup.py                # ロガーのセットアップ (setup_logger関数)
│   │
│   ├── utils/
│   │   └── file_manager.py         # ファイルパス管理（FilePathManagerクラス）
│   └── requirements.txt            # image_acquisitionに必要なパッケージのリスト
│
├── config.yml                      # 全体の設定ファイル
└── main.py                         # エントリーポイントとなるスクリプト
```

## 設定方法

`config.example.yml`を元に`config.yml`を作成する
```config.yml
# データ取得前半の設定
image_acquisition:
  data_dirpath: './data' # 取得されたデータを保存するディレクトリのパス
  save_to_csv: true # trueにすると画像のメタデータをCSVに保存する
  send_to_db: true # trueにすると画像のメタデータをInfluxDBに送信する

# カメラの設定（複数カメラに対応）
camera:
  - camera_index: 0
    width: 320
    height: 240
    fps: 30
  - camera_index: 1
    width: 320
    height: 240
    fps: 30

# InfluxDBについての設定
influxdb:
  url: 'http://localhost:8086'
  token: '<your_db_token>'
  org: '<your_org>'
  bucket: '<your_bucket>'
```

## 実行方法

以下のコマンドを実行すると、画像データの取得が始まる。
```
python3 main.py
```

## 取得されるデータの構造の例
```
session_20240919_212704/
│
├── camera0/
│   ├── 2024-09-19/
│   │   └── 12/
│   │       ├── 27/
│   │       │   ├── camera0_2024-09-19_12-27-06_0.jpg
│   │       │   ├── camera0_2024-09-19_12-27-06_1.jpg
│   │       │   ├── ...
│   │       │   └── camera0_2024-09-19_12-27-59_29.jpg
│   │       └── 28/
│   │           ├── camera0_2024-09-19_12-28-00_0.jpg
│   │           ├── ...
│   │           └── camera0_2024-09-19_12-28-59_29.jpg
│   └── meta_data.csv
│
└─ camera1/
    ├── 2024-09-19/
    │   └── 12/
    │       ├── 27/
    │       │   ├── camera1_2024-09-19_12-27-06_0.jpg
    │       │   ├── camera1_2024-09-19_12-27-06_1.jpg
    │       │   ├── ...
    │       │   └── camera1_2024-09-19_12-27-59_29.jpg
    │       └── 28/
    │           ├── camera1_2024-09-19_12-28-00_0.jpg
    │           ├── ...
    │           └── camera1_2024-09-19_12-28-59_29.jpg
    └── meta_data.csv

```