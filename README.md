# MangaVox Annotation Tool
<img src="./docs/logo.png" alt="Logo image of MangaVox annotator" width="30%;"></img>

MangaVoxの音声データに対するアノテーションツール．
このツールでは，以下のアノテーションが可能．
- 音声に対するアノテーション（アノテーション用XMLのaligned_voice要素）の修正
    - 発話の開始・終了時刻の修正
    - 発話のテキストの修正
    - 発話のキャラクタ・演技者の修正
    - 音声ファイルIDの修正
- 漫画画像上のバウンディングボックスとの対応付け
    - 漫画画像上のバウンディングボックス（frame, text, face, body要素）とaligned_voice要素との対応付け
    - 漫画画像のページ番号とaligned_voice要素の対応付け

## 画面例
### 全体音声アノテーションモード（full mode）
![全体音声アノテーションモード](./docs/interface_sample_full.jpg)

### 発話単位音声アノテーションモード（utt mode）
![発話単位音声アノテーションモード](./docs/interface_sample_utt.jpg)

## 必要条件
- Python 3.12以上
- Pythonパッケージ管理ソフトuv

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
    - 発話単位の音声データは`data/manga2voice/concatenated_voices`ディレクトリに配置
    - ダウンロードしたメタデータのXMLファイル（`voice`要素を含む公開形式）は`data/workspace/${MANGA_TITLE}.xml`として配置
5. MangaVoxのメタデータをManga109のメタデータと結合
    - `config.py`の`MANGA_TITLES`に含まれる全作品について，公開形式のXMLをアノテーション形式の`*_v1.xml`に変換
    ```bash
    uv run python -m scripts.merge_with_manga109_annotations
    ```
    - 既存の`*_v1.xml`を更新する場合は`--overwrite`を指定
    - 一部の作品だけ実施する場合は，例えば`uv run python -m scripts.merge_with_manga109_annotations --titles AkkeraKanjinchou HinagikuKenzan`
    - 単作品だけ従来どおり指定する場合は，`uv run python -m scripts.merge_with_manga109_annotations data/workspace/${MANGA_TITLE}.xml data/manga109/Manga109_released_2023_12_07/annotations/${MANGA_TITLE}.xml data/workspace/${MANGA_TITLE}_v1.xml`
6. 各トラックを混合した音声ファイルを作成
    - `config.py`の`MANGA_TITLES`に含まれる全作品を処理する場合
    ```bash
    uv run python -m scripts.mix_mangavox_audio
    ```
    - 現在のデータが`concatenated_voices_v2`にある場合は，入力ルートを指定
    ```bash
    uv run python -m scripts.mix_mangavox_audio \
        --audio-root data/manga2voice/concatenated_voices_v2 \
        --overwrite
    ```
    - 出力は`data/manga2voice/voices/<manga_title>_ALL.flac`として作成される
    - `*_Gaya.flac`はガヤとして扱い，通常はデフォルトで`-40 dB`に下げる
    - `config.py`の`GAYA_UTT_GAINS_IN_DB`にあるvoice id区間は，前後に少しマージンを付けて指定dBで混合する

### アノテーションツール起動 & 実施
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
            - `full`モードの場合は音声ファイルのパス（例: `data/manga2voice/voices/AkkeraKanjinchou_ALL.flac`）
            - `utt`モードの場合は音声ファイルのディレクトリのパス（例: `data/manga2voice/concatenated_voices/AkkeraKanjinchou`）
        - 例
            - fullモードの場合
                ```bash
                MANGA_TITLE="AkkeraKanjinchou"
                python launch.py full --image_root data/manga109/Manga109_released_2023_12_07/images/${MANGA_TITLE} data/workspace/${MANGA_TITLE}_v1.xml data/manga2voice/voices/${MANGA_TITLE}_ALL.flac
                ```
            - uttモードの場合
                ```bash
                MANGA_TITLE="AkkeraKanjinchou"
                python launch.py utt --image_root data/manga109/Manga109_released_2023_12_07/images/${MANGA_TITLE} data/workspace/${MANGA_TITLE}_v1.xml data/manga2voice/concatenated_voices/${MANGA_TITLE}
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
    uv run python -m scripts.update_mangavox_annotations --change_log_dir logs/${MODE} data/workspace/${MANGA_TITLE}_v1.xml data/workspace/${MANGA_TITLE}_v2.xml
    ```
2. (Optional) XMLファイルがどのように更新されたかのリストを作成
    ```bash
    uv run python -m scripts.create_change_list data/workspace/${MANGA_TITLE}_v1.xml data/workspace/${MANGA_TITLE}_v2.xml "data/workspace/${MANGA_TITLE}/change_log_v2-v1.yaml"
    ```

### 統計量の生成
Appendixの統計表を再生成する場合は以下を実行．
```bash
uv run python -m scripts.generate_annotation_stats data/workspace/*_v2.xml --audio-root data/manga2voice/concatenated_voices
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

## Citation
このツールを使う際は、以下の論文を引用してください。

```bibtex
@inproceedings{STakamichi2026ICASSP,
    author = "Takamichi, Shinnosuke and Nakamura, Tomohiko and Suda, Hitoshi and Fukayama, Satoru and Ogata, Jun",
    booktitle = "Proceedings of IEEE International Conference on Acoustics, Speech, and Signal Processing (ICASSP)",
    title = "MangaVox: {Dataset} of acted voices aligned with manga images towards computer understanding of audio comics",
    pages = "19467--19471",
    month = "May",
    year = "2026",
    doi = "10.1109/ICASSP55912.2026.11463396"
}
```

## License
このツールのライセンスはMIT Licenseです。
MangaVoxのライセンスは別ですのでご注意ください。
Manga109のデータは、Manga109のライセンスに従って利用してください。


# Appendix

## 作品一覧
| 作品名 | 年代 | ジャンル | 作品の時間長 [h] | 発話時間の合計 [h] | キャラ | 演技者数（男性）| 演技者数（女性） | 発話数 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| ラブひな | 1990s | ラブコメ | 1.8 | 1.3 | 14 | 1 | 2 | 2270 |
| ひなぎく見参！一本桜花町編 | 2000s | 恋愛 | 1.3 | 0.8 | 16 | 1 | 3 | 1282 |
| サラダデイズ | 1990s | 恋愛 | 1.6 | 1.0 | 27 | 3 | 4 | 1719 |
| エヴリデイおさかなちゃん | 1990s | 動物 | 2.3 | 1.5 | 44 | 1 | 2 | 2336 |
| やさしい悪魔 | 1990s | ファンタジー | 2.2 | 1.4 | 28 | 3 | 2 | 1694 |
| 太陽にスマッシュ！ | 2000s | スポーツ | 1.3 | 0.8 | 15 | 2 | 2 | 1202 |
| あっけら貫刃帖 | 2000s | バトル | 1.6 | 1.1 | 27 | 3 | 3 | 1619 |
| あくはむ | 2000s | 4コマ | 1.8 | 1.1 | 35 | 1 | 3 | 2036 |
|  |  |  |  |  |  |  |  |  |
| 8作品 | 2種の年代 | 7ジャンル | 14.0 | 9.0 | 206 | 9 | 9 | 14158 |


## 発話とManga109のframe, text, face, body要素との対応付け数
| 作品名 | 対応付けられたframe要素の数 | 対応付けられたtext要素の数 | 対応付けられたface要素の数 | 対応付けられたbody要素の数 |
|:---:|:---:|:---:|:---:|:---:|
| ラブひな | 2248 | 1943 | 1598 | 1911 |
| ひなぎく見参！一本桜花町編 | 1230 | 947 | 647 | 936 |
| サラダデイズ | 1700 | 1331 | 913 | 1251 |
| エヴリデイおさかなちゃん | 2287 | 1926 | 608 | 929 |
| やさしい悪魔 | 1677 | 1587 | 952 | 1077 |
| 太陽にスマッシュ！ | 1192 | 928 | 743 | 853 |
| あっけら貫刃帖 | 1653 | 1349 | 820 | 1020 |
| あくはむ | 1861 | 1431 | 1251 | 1619 |
|  |  |  |  |  |
| 8作品 | 13848 | 11442 | 7532 | 9596 |


## 発話要素（voice/aligned_voice）の主な属性一覧表
|属性名|内容|必須か否か|値の例|
|:---:|:---:|:---:|:---:|
|id|発話固有ID|&check;|60000027|
|index|発話順序インデックス|&check;|38|
|start|発話開始時刻 [s]|&check;|161.095|
|end|発話終了時刻 [s]|&check;|161.635|
|episode_index|作品内での話数インデックス|&check;|1|
|page_index|ページインデックス|&check;|4|
|actor_id|演技者ID|&check;|08F20|
|character_id|キャラクタID|&check;|00001d7b|
|audio_id|音声ファイルID|&check;|08F20_Sakisuke|
|text_id|Manga109のtext要素のID|-|00001d93|
|frame_id|Manga109のframe要素のID|-|00001d96|
|face_id|Manga109のface要素のID|-|00001dc2|
|body_id|Manga109のbody要素のID|-|00001d94|


