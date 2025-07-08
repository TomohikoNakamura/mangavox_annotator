# MangaVox Annotation Tool

## 概要
Manga109の画像データと，MangaVoxの音声データとメタデータを対応付けるためのアノテーションツール．

## デモ
<!--
![screenshot](docs/screenshot.png)
-->

## 必要条件
- Python 3.12以上
- Manga109画像・メタデータ
- MangaVox音声・メタデータ

## インストール
1. リポジトリをクローン
    ```bash
    git clone https://github.com/TomohikoNakamura/mangavox_annotator.git
    cd mangavox_annotator
    ```
2. uvで環境構築
    ```bash
    uv sync
    ```

## Getting Started
### 事前準備
1. リポジトリのクローン
    ```bash
    git clone https://github.com/TomohikoNakamura/mangavox_annotator.git
    cd mangavox_annotator
    ```
2. uvで環境構築
    ```bash
    uv sync
    ```
3. `manga109`の画像・メタデータを用意
    - 画像データは`data/manga109/Manga109_released_2023_12_07/images/<manga_title>`に配置
    - メタデータのXMLファイルは`data/manga109/Manga109_released_2023_12_07/annotations/<manga_title>.xml`として配置
4. `mangavox`のデータの準備
    - 音声データは`data/manga2voice/concatenated_voices`ディレクトリに配置
        - 全ての音声が混合された音声ファイルは，FLACからMP3に変換したものも用意し，`data/manga2voice/voices/<manga_title>_ALL.mp3`として配置
    - メタデータのXMLファイルは`data/workspace`ディレクトリに配置
5. MangaVoxのメタデータをManga109のメタデータと結合．
    - アノテーションした漫画作品のXMLファイルで以下を全て実施
    ```bash
    MANGA_TITLE="AkkeraKanjinchou" # 例としてAkkeraKanjinchouを使用
    uv run python merge_with_manga109_annotations.py data/workspace/${MANGA_TITLE}.xml data/manga109/Manga109_released_2023_12_07/annotations/${MANGA_TITLE}.xml data/workspace/${MANGA_TITLE}_revised.xml
    ```

### アノテーションツール起動
- 1. サーバ起動
    - 簡単起動Bashスクリプトを使用する場合
        ```bash
        bash easy_launch.sh <mode> <manga_index>
        ```
        - `<mode>`：`full`または`utt`を指定
        - `<manga_index>`：Manga109のインデックス番号を指定
            1. AkkeraKanjinchou
            2. Akuhamu
            3. EverydayOsakanaChan
            4. HinagikuKenzan
            5. LoveHina_vol01
            6. SaladDays_vol01
            7. TaiyouNiSmash
            8. YasasiiAkuma
    - コマンドの使い方
        ```bash
        python launch.py <mode> --image_root <image_root> <xml_path> <audio_path>
        ```
        - `<mode>`：`full`または`utt`を指定
        - `<image_root>`：漫画画像のディレクトリのパス
        - `<xml_path>`：アノテーション用のXMLファイルのパス
        - `<audio_path>`：音声ファイルのパス
            - `full`モードの場合は音声ファイルのパス（例: `data/manga2voice/voices/AkkeraKanjinchou_ALL.mp3`）
            - `utt`モードの場合は音声ファイルのディレクトリのパス（例: `data/manga2voice/concatenated_voices/AkkeraKanjinchou`）
        - 例
            - fullモードの場合
                ```bash
                MANGA_TITLE="AkkeraKanjinchou"
                python launch.py full --image_root data/manga109/Manga109_released_2023_12_07/images/${MANGA_TITLE} data/workspace/${MANGA_TITLE}_revised.xml data/manga2voice/voices/${MANGA_TITLE}_ALL.mp3
                ```
            - uttモードの場合
                ```bash
                MANGA_TITLE="AkkeraKanjinchou"
                python launch.py utt --image_root data/manga109/Manga109_released_2023_12_07/images/${MANGA_TITLE} data/workspace/${MANGA_TITLE}_revised.xml data/manga2voice/concatenated_voices/${MANGA_TITLE}
                ```
    - オプション
        - 第一引数：モード
            - `full`: 作品全体の音声を表示
            - `utt`: 音声アノテーション（発話単位）で表示
        - `--image_root`: 画像ディレクトリのパス
        - `--xml_path`: XMLファイルのパス
        - `--audio_path`: 音声ファイルのパス
- 2. ブラウザで`http://localhost:8000`にアクセス
- 3. アノテーションを行い，そのログが`logs/<mode>/<manga_title>`ディレクトリに保存される．

### 変更ログを元にXMLを更新
1. 変更ログファイルを元にXMLを更新
    ```bash
    MODE="full" # または "utt"
    MANGA_TITLE="AkkeraKanjinchou" # 例としてAkkeraKanjinchouを使用
    uv run python update_mangavox_annotations.py --change_log_dir logs/${MODE} data/workspace/${MANGA_TITLE}_revised.xml data/workspace/${MANGA_TITLE}_revised_v2.xml
    ```

## アノテーションツールの操作

### 操作
- `space`: 音声の再生/停止
- `n`: 次のリージョンを選択
- `b`: 前のリージョンを選択
- `s`: 選択したリージョンのアノテーションの変更内容を保存
- `h`: ヘルプの表示/非表示
- マウスホイール: 波形をズームイン/アウト
- 波形をクリック: 現在のリージョンを選択解除
- リージョンをクリック: クリックしたリージョンを選択
- キャンバスをクリック: マウスの位置を含む最小のバウンディングボックスを選択して対応付け

### Interface
1. 波形パネル
    - キーボードまたはマウスで波形を操作。
    - ズームスライダーで波形解像度を調整可能。
2. 漫画画像パネル
    - 漫画ページ上でアノテーションをインタラクティブに表示。
    - バウンディングボックスをクリックして、音声リージョンと関連付け。
3. アノテーションパネル
    - 選択されたリージョンのアノテーションを編集。
    - アノテーションを保存・リセット可能。

### Annotation Workflow
1. データを読み込み：漫画画像、アノテーション、音声データをバックエンド経由でロードします。
2. ナビゲート：波形を使用して音声リージョンをナビゲート。
3. アノテート
    - 波形上でリージョンを選択。またはn/bキーで次/前のリージョンを選択。
    - 画像上でバウンディングボックスをクリックし、音声リージョンに対応付け。
    - 必要に応じてアノテーションパネルで詳細を編集。
    - 保存ボタン（sキー）で変更を保存。
    - 変更ログファイルとして`logs/<mode>/<manga_title>/change_log.yaml`に出力。
4. 変更の反映：変更ログファイルを使ってXMLファイルを更新。

## Authors
- [Tomohiko Nakamura](https://github.com/TomohikoNakamura)

## License
MIT License

## Acknowledgements
