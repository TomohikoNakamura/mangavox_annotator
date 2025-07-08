# MangaVox Annotation Tool
## 概要
Manga109の画像データと，MangaVoxの音声データとメタデータを対応付けるためのアノテーションツール．
サーバクライアント式で，サーバはFastAPI，フロントエンドはjavascriptで実装．

## 起動方法
- 0. 事前準備
    - `manga109`の画像データを用意
        - 例: `data/manga109/Manga109_released_2023_12_07/images/AkkeraKanjinchou`
    - `mangavox`のデータの準備
        - 音声データは`data/manga2voice/concatenated_voices`ディレクトリに配置
        - アノテーション用のXMLファイルは`data/workspace`ディレクトリに配置（XMLファイルは，manga109のメタデータとマージ済み）
- 1. uvで環境構築
- 2. サーバ起動
    - 簡単起動シェル
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
                python launch.py full --image_root data/manga109/Manga109_released_2023_12_07/images/${MANGA_TITLE} data/workspace/${MANGA_TITLE}_revised_v5.xml data/manga2voice/voices/${MANGA_TITLE}_ALL.mp3
                ```
            - uttモードの場合
                ```bash
                MANGA_TITLE="AkkeraKanjinchou"
                python launch.py utt --image_root data/manga109/Manga109_released_2023_12_07/images/${MANGA_TITLE} data/workspace/${MANGA_TITLE}_revised_v5.xml data/manga2voice/concatenated_voices/${MANGA_TITLE}
                ```
    - オプション
        - 第一引数：モード
            - `full`: 作品全体の音声を表示
            - `utt`: 音声アノテーション（発話単位）で表示
        - `--image_root`: 画像ディレクトリのパス
        - `--xml_path`: XMLファイルのパス
        - `--audio_path`: 音声ファイルのパス
- 3. ブラウザで`http://localhost:8000`にアクセス
- 4. アノテーションを行い，そのログが`logs`ディレクトリに保存される．更新したXML自体は保存されないので，必要に応じて変更ログから作成する．

## ブラウザ上での使用方法
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

### インターフェース
1. 波形パネル
    - キーボードまたはマウスで波形を操作。
    - ズームスライダーで波形解像度を調整可能。
2. 漫画画像パネル
    - 漫画ページ上でアノテーションをインタラクティブに表示。
    - バウンディングボックスをクリックして、音声リージョンと関連付け。
3. アノテーションパネル
    - 選択されたリージョンのアノテーションを編集。
    - アノテーションを保存・リセット可能。

### アノテーション手順
- データを読み込み: 漫画画像、アノテーション、音声データをバックエンド経由でロードします。
- ナビゲート: 波形を使用して音声リージョンをナビゲート。
- アノテート:
    - 波形上でリージョンを選択。またはn/bキーで次/前のリージョンを選択。
    - 画像上でバウンディングボックスをクリックし、音声リージョンに対応付け。
    - 必要に応じてアノテーションパネルで詳細を編集。
    - 保存: 保存 ボタンまたはsキーで変更を保存。

# LICENSE
MIT License