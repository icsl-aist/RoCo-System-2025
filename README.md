# Akari Kachaka RoCo System

Akari（司令塔ロボット）とKachaka（自律移動ロボット）が、大規模言語モデル（GPT-4o）を通じて対話し、物理世界で協力してタスクを遂行するための実験システムです。

## 📖 プロジェクト概要

本システムは、物理的な制約を持つ2つのエージェントが、自然言語による推論を用いて状況判断を行い、ゴール（例：冷蔵庫前への到達）を目指します。

### 🤖 エージェントの役割
- **Akari**
  - **役割:** 全体の進捗管理、戦略立案、高度な認識（外部PCによる障害物検知など）。
  - **特徴:** 自分では移動できないため、Kachakaに指示を出して運搬・ドッキングを依頼します。
  - **制御:** SSH経由で外部PC上の推論スクリプトや音声合成を実行します。

- **Kachaka**
  - **役割:** 移動、家具（シェルフ）の運搬、物理的なアクションの実行。
  - **特徴:** Akariの指示に従い、具体的な物理動作（移動座標の計算、ドッキングなど）を行います。
  - **制御:** `kachaka-api` を使用して直接制御します。

## 📂 ディレクトリ構成

```text
.
├── main.py                     # システムのエントリーポイント（メインループ）
├── function_list_akari.py      # Akari制御用（SSH経由で外部プロセス呼び出し）
├── function_list_kachaka.py    # Kachaka制御用（ハードウェアAPIラッパー）
├── usage_tokens.py             # OpenAI APIトークン使用量の計測
├── token_usage.log             # トークン使用量の記録ログ（自動生成）
├── logic/                      # ロジック
│   ├── llm_client.py           # OpenAI APIクライアント
│   ├── prompt_loader.py        # JSONプロンプトの読み込み・整形
│   ├── world_state.py          # 世界状態（座標、フラグ）の管理
│   └── formatter.py            # ログ表示用の整形ユーティリティ
└── prompts/                    # LLM用プロンプト定義（JSON）
    ├── akari_prompt.json       # Akariの性格・ルール・出力定義
    └── kachaka_prompt.json     # Kachakaの物理制約・行動指針定義
```
## セットアップ

### 必須ライブラリ
付属の `requirements.txt` を使用して、必要なパッケージをインストールしてください。

```bash
pip install -r requirements.txt
```

### ハードウェア接続要件
- **Kachaka**: APIが有効化されており、ネットワーク経由で制御可能であること。
- **Akari (または外部PC)**: SSH接続が可能で、以下のパスにYOLO推論環境および音声合成環境が構築されていること。
  - リモートパス: `/home/aitclab2011/test/akari_yolo_inference2(2025.10.2)/final_project` など
  - 障害物検知などの該当ファイルが入っているAkariを使用すること("1"と書かれたシールが貼ってあるAkari)



### 1. OpenAI APIキーの設定
システムはGPT-4oを使用するため、APIキーが必要です。環境変数として設定してください。（APIキーは研究室のデスクトップPC内に保存）

**Mac/Linux:**
```bash
export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
```


### 2. ネットワーク設定 (IPアドレス)
実験環境のIPアドレスがコード内にハードコードされています。環境が変わる場合は以下のファイルを修正してください。

- **`function_list_kachaka.py`**:
  ```python
  # デフォルト設定値
  client = kachaka_api.KachakaApiClient("172.31.14.25:26400")
  ```

- **`function_list_akari.py`**:
  ```python
  # デフォルト設定値
  hostname = "172.31.14.46"
  username = "aitclab2011"
  password = "aitclab2011"
  ```

## 実行方法

プロジェクトのルートディレクトリで以下のコマンドを実行してください。

```bash
python main.py
```

### 実行後の挙動
1. **初期化**: ロボットの位置情報や状態がリセットされます。
2. **推論ループ開始**: 
   - Akariが現状を分析し、Kachakaへ指示（`CALL`, `ASK to carry` 等）を出します。
   - Kachakaはその指示を物理アクション（`MOVE`, `DOCK` 等）に変換して実行します。
3. **障害物検知**: 
   - 移動経路に関連する障害物がある場合、SSH経由で外部カメラによるチェックが行われます。
4. **終了条件**: 
   - ゴール条件（Akariと共に目的地へ到着）を満たすか、最大ステップ数（30ステップ）に達すると終了します。

## ログとデバッグ (Logging)

- **コンソール出力**: 
  各ステップでの「Akariの提案」「Kachakaの応答」「現在地座標」などがリアルタイムで表示されます。
  
- **トークン使用量**: 
  `token_usage.log` に実行ごとのトークン消費量（Prompt/Completion/Total）が追記されます。コスト管理にご活用ください。

## 注意事項

- **SSHコマンドのパス**: `function_list_akari.py` 内のリモートスクリプトパスは、特定の実験環境（`/home/aitclab2011/...`）に固定されています。環境移行時は必ず修正してください。
- **安全性**: 実機が動作します。ドッキングや障害物回避の動作が含まれるため、ロボットの周囲に十分なスペースを確保して実行してください。
