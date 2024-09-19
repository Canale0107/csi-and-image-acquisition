# Image Acquisition

## 実行方法
```
python3 main.py
```

## ファイル構成

```
src/
│
├── camera/
│   ├── camera_manager.py       # カメラの管理（CameraManagerクラス）
│   └── image.py                # 画像の保存やメタデータの管理（Imageクラス、ImageMetaDataクラス）
│
├── data_acquisition/
│   ├── acquisition_manager.py  # データ取得管理（DataAcquisitionManagerクラス、run_acquisition_for_camera関数）
│   ├── file_manager.py         # ファイルパス管理（FilePathManagerクラス）
│
├── writers/
│   ├── abstract_writer.py      # 抽象クラス（DataWriter, DataManagerの抽象クラス）
│   ├── csv_writer.py           # CSVWriter, CSVManagerクラス
│   └── db_writer.py            # InfluxDBWriter, DBManagerクラス
│
├── config/
│   └── config_loader.py        # 設定ファイルの読み込み（load_configs関数）
│
└── requirements.txt            # 必要なパッケージのリスト
```