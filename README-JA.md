<div align="center">

<img src="static/image/logo_compressed.png" alt="Weibo Public Opinion Analysis System Logo" width="100%">

<a href="https://trendshift.io/repositories/15286" target="_blank"><img src="https://trendshift.io/api/badge/repositories/15286" alt="666ghj%2FBettaFish | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

<a href="https://leaflow.net/" target="_blank"><img src="static/image/Leaflow_logo.png" alt="666ghj%2FWeibo_PublicOpinion_AnalysisSystem | Leaflow" style="width: 150px;" width="150"/></a>

[![GitHub Stars](https://img.shields.io/github/stars/666ghj/Weibo_PublicOpinion_AnalysisSystem?style=flat-square)](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem/stargazers)
[![GitHub Watchers](https://img.shields.io/github/watchers/666ghj/Weibo_PublicOpinion_AnalysisSystem?style=flat-square)](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem/watchers)
[![GitHub Forks](https://img.shields.io/github/forks/666ghj/Weibo_PublicOpinion_AnalysisSystem?style=flat-square)](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem/network)
[![GitHub Issues](https://img.shields.io/github/issues/666ghj/Weibo_PublicOpinion_AnalysisSystem?style=flat-square)](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/666ghj/Weibo_PublicOpinion_AnalysisSystem?style=flat-square)](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem/pulls)

[![GitHub License](https://img.shields.io/github/license/666ghj/Weibo_PublicOpinion_AnalysisSystem?style=flat-square)](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem/blob/main/LICENSE)
[![Version](https://img.shields.io/badge/version-v1.0.0-green.svg?style=flat-square)](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem)
[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)


[English](./README-EN.md) | [中文文档](./README.md) | [日本語](./README-JA.md)

</div>

## ⚡ プロジェクト概要

**「BettaFish」** は、ゼロから構築された革新的なマルチエージェント世論分析システムです。情報の繭を破り、本来の世論を復元し、将来のトレンドを予測し、意思決定を支援します。ユーザーは、チャットのように分析ニーズを提起するだけで、エージェントが国内外の30以上の主流ソーシャルプラットフォームと数百万のパブリックコメントを自動的に分析します。

> ベタは、小さくても闘争的で美しい魚であり、「小さくても強力で、挑戦を恐れない」ことを象徴しています。

システムが生成した「武漢大学の世論」に関する研究レポートをご覧ください: [武漢大学のブランド評判に関する詳細分析レポート](./final_reports/final_report__20250827_131630.html)

レポートの品質だけでなく、類似製品と比較して、🚀 6つの主要な利点があります:

1. **AI駆動の包括的監視**: AIクローラークラスターが24時間365日稼働し、Weibo、Xiaohongshu、TikTok、Kuaishouなど、国内外の10以上の主要ソーシャルメディアプラットフォームを包括的にカバーします。トレンドコンテンツをリアルタイムでキャプチャするだけでなく、大量のユーザーコメントにも掘り下げ、最も本物で広範な世論の声を聞くことができます。

2. **LLMを超えた複合分析エンジン**: 専門的に設計された5種類のエージェントに依存するだけでなく、微調整モデルや統計モデルなどのミドルウェアも統合します。マルチモデルの協調作業により、分析結果の深さ、精度、多次元の視点を保証します。

3. **強力なマルチモーダル機能**: テキストと画像の制限を突破し、TikTok、Kuaishouなどの短編ビデオコンテンツを深く分析し、最新の検索エンジンから天気、カレンダー、株式などの構造化されたマルチモーダル情報カードを正確に抽出し、世論のダイナミクスを完全に制御できます。

4. **エージェント「フォーラム」コラボレーションメカニズム**: 異なるエージェントに独自のツールセットと思考パターンを付与し、討論司会者モデルを導入し、「フォーラム」メカニズムを通じて思考連鎖の衝突と討論を実施します。これにより、単一モデルの思考の制限やコミュニケーションによる同質化を回避するだけでなく、より高品質の集合知と意思決定サポートも促進します。

5. **公開ドメインとプライベートドメインデータのシームレスな統合**: プラットフォームは世論を分析するだけでなく、内部ビジネスデータベースと世論データのシームレスな統合をサポートする高セキュリティインターフェースも提供します。データの障壁を突破し、垂直ビジネスに「外部トレンド+内部インサイト」の強力な分析機能を提供します。

6. **軽量で高度に拡張可能なフレームワーク**: 純粋なPythonモジュール設計に基づき、軽量でワンクリックデプロイメントを実現します。明確なコード構造により、開発者はカスタムモデルやビジネスロジックを簡単に統合でき、プラットフォームの迅速な拡張と深いカスタマイズが可能になります。

**世論から始まりますが、世論に限定されません**。「WeiYu」の目標は、すべてのビジネスシナリオを駆動するシンプルで汎用的なデータ分析エンジンになることです。

> たとえば、エージェントツールセットのAPIパラメーターとプロンプトを簡単に変更するだけで、金融市場分析システムに変換できます。

<div align="center">
<img src="static/image/system_schematic.png" alt="banner" width="800">

従来のデータダッシュボードに別れを告げます。「WeiYu」では、すべてがシンプルな質問から始まります - 会話のように分析ニーズを尋ねるだけです
</div>

## 🏗️ システムアーキテクチャ

### 全体アーキテクチャ図

**Insight Agent** プライベートデータベースマイニング: プライベート世論データベースの詳細分析用AIエージェント

**Media Agent** マルチモーダルコンテンツ分析: 強力なマルチモーダル機能を持つAIエージェント

**Query Agent** 正確な情報検索: 国内外のWeb検索機能を備えたAIエージェント

**Report Agent** インテリジェントレポート生成: 組み込みテンプレートを使用したマルチラウンドレポート生成AIエージェント

<div align="center">
<img src="static/image/framework.png" alt="banner" width="800">
</div>

### 完全な分析ワークフロー

| ステップ | フェーズ名 | 主な操作 | 参加コンポーネント | サイクル性質 |
|------|------------|-----------------|-------------------------|--------------|
| 1 | ユーザークエリ | Flaskメインアプリケーションがクエリを受信 | Flaskメインアプリケーション | - |
| 2 | 並列起動 | 3つのエージェントが同時に作業を開始 | Query Agent、Media Agent、Insight Agent | - |
| 3 | 予備分析 | 各エージェントが専用ツールを使用して概要検索を実行 | 各エージェント + 専用ツールセット | - |
| 4 | 戦略策定 | 予備結果に基づいてセグメント化された研究戦略を開発 | 各エージェントの内部決定モジュール | - |
| 5-N | **反復フェーズ** | **フォーラムコラボレーション + 詳細研究** | **ForumEngine + すべてのエージェント** | **マルチラウンドサイクル** |
| 5.1 | 詳細研究 | 各エージェントがフォーラムホストの指導の下で専門的な検索を実施 | 各エージェント + リフレクションメカニズム + フォーラムガイダンス | 各サイクル |
| 5.2 | フォーラムコラボレーション | ForumEngineがエージェント通信を監視し、ホストサマリーを生成 | ForumEngine + LLMホスト | 各サイクル |
| 5.3 | コミュニケーション統合 | 各エージェントが討論に基づいて研究方向を調整 | 各エージェント + forum_readerツール | 各サイクル |
| N+1 | 結果統合 | Report Agentがすべての分析結果とフォーラムコンテンツを収集 | Report Agent | - |
| N+2 | レポート生成 | テンプレートとスタイルを動的に選択し、複数回を通じて最終レポートを生成 | Report Agent + テンプレートエンジン | - |

### プロジェクトコード構造ツリー

```
Weibo_PublicOpinion_AnalysisSystem/
├── QueryEngine/                   # 国内外のニュース広範囲検索Agent
│   ├── agent.py                   # Agentメインロジック
│   ├── llms/                      # LLMインターフェースラッパー
│   ├── nodes/                     # 処理ノード
│   ├── tools/                     # 検索ツール
│   ├── utils/                     # ユーティリティ関数
│   └── ...                        # その他のモジュール
├── MediaEngine/                   # 強力なマルチモーダル理解Agent
│   ├── agent.py                   # Agentメインロジック
│   ├── nodes/                     # 処理ノード
│   ├── llms/                      # LLMインターフェース
│   ├── tools/                     # 検索ツール
│   ├── utils/                     # ユーティリティ関数
│   └── ...                        # その他のモジュール
├── InsightEngine/                 # プライベートデータベースマイニングAgent
│   ├── agent.py                   # Agentメインロジック
│   ├── llms/                      # LLMインターフェースラッパー
│   │   └── base.py                # 統合OpenAI互換クライアント
│   ├── nodes/                     # 処理ノード
│   │   ├── base_node.py           # 基本ノードクラス
│   │   ├── formatting_node.py     # フォーマットノード
│   │   ├── report_structure_node.py # レポート構造ノード
│   │   ├── search_node.py         # 検索ノード
│   │   └── summary_node.py        # サマリーノード
│   ├── tools/                     # データベースクエリと分析ツール
│   │   ├── keyword_optimizer.py   # Qwenキーワード最適化ミドルウェア
│   │   ├── search.py              # データベース操作ツールキット
│   │   └── sentiment_analyzer.py  # センチメント分析統合ツール
│   ├── state/                     # 状態管理
│   │   ├── __init__.py
│   │   └── state.py               # エージェント状態定義
│   ├── prompts/                   # プロンプトテンプレート
│   │   ├── __init__.py
│   │   └── prompts.py             # 各種プロンプト
│   └── utils/                     # ユーティリティ関数
│       ├── __init__.py
│       ├── config.py              # 設定管理
│       └── text_processing.py     # テキスト処理ツール
├── ReportEngine/                  # マルチラウンドレポート生成Agent
│   ├── agent.py                   # Agentメインロジック
│   ├── llms/                      # LLMインターフェース
│   ├── nodes/                     # レポート生成ノード
│   │   ├── template_selection.py  # テンプレート選択ノード
│   │   └── html_generation.py     # HTML生成ノード
│   ├── report_template/           # レポートテンプレートライブラリ
│   │   ├── 社会公共热点事件分析.md
│   │   ├── 商业品牌舆情监测.md
│   │   └── ...                    # その他のテンプレート
│   └── flask_interface.py         # Flask APIインターフェース
├── ForumEngine/                   # フォーラムエンジンシンプル実装
│   ├── monitor.py                 # ログ監視とフォーラム管理
│   └── llm_host.py                # フォーラムホストLLMモジュール
├── MindSpider/                    # Weiboクローラーシステム
│   ├── main.py                    # クローラーメインプログラム
│   ├── config.py                  # クローラー設定ファイル
│   ├── BroadTopicExtraction/      # トピック抽出モジュール
│   │   ├── database_manager.py    # データベースマネージャー
│   │   ├── get_today_news.py      # 今日のニュース取得
│   │   ├── main.py                # トピック抽出メインプログラム
│   │   └── topic_extractor.py     # トピック抽出器
│   ├── DeepSentimentCrawling/     # 詳細センチメントクローリング
│   │   ├── keyword_manager.py     # キーワードマネージャー
│   │   ├── main.py                # 詳細クローリングメインプログラム
│   │   ├── MediaCrawler/          # メディアクローラーコア
│   │   └── platform_crawler.py    # プラットフォームクローラー管理
│   └── schema/                    # データベーススキーマ
│       ├── db_manager.py          # データベースマネージャー
│       ├── init_database.py       # データベース初期化
│       └── mindspider_tables.sql  # データベーステーブル構造
├── SentimentAnalysisModel/        # センチメント分析モデルコレクション
│   ├── WeiboSentiment_Finetuned/  # 微調整BERT/GPT-2モデル
│   ├── WeiboMultilingualSentiment/# 多言語センチメント分析(推奨)
│   ├── WeiboSentiment_SmallQwen/  # 小パラメータQwen3微調整
│   └── WeiboSentiment_MachineLearning/ # 従来の機械学習手法
├── SingleEngineApp/               # 個別エージェントStreamlitアプリケーション
│   ├── query_engine_streamlit_app.py
│   ├── media_engine_streamlit_app.py
│   └── insight_engine_streamlit_app.py
├── templates/                     # Flaskテンプレート
│   └── index.html                 # メインインターフェースフロントエンド
├── static/                        # 静的リソース
├── logs/                          # ランタイムログディレクトリ
├── final_reports/                 # 最終生成HTMLレポートファイル
├── utils/                         # 共通ユーティリティ関数
│   ├── forum_reader.py            # エージェントフォーラム通信
│   └── retry_helper.py            # ネットワークリクエスト再試行メカニズムツール
├── app.py                         # Flaskメインアプリケーションエントリ
├── config.py                      # グローバル設定ファイル
└── requirements.txt               # Python依存関係リスト
```

## 🚀 クイックスタート

> エージェントシステムの構築が初めての場合は、非常にシンプルなデモから始めることができます: [Deep Search Agent Demo](https://github.com/666ghj/DeepSearchAgent-Demo)

### システム要件

- **オペレーティングシステム**: Windows、Linux、MacOS
- **Pythonバージョン**: 3.9+
- **Conda**: AnacondaまたはMiniconda
- **データベース**: MySQL(オプション、クラウドデータベースサービスを選択できます)
- **メモリ**: 2GB+推奨

### 1. Conda環境の作成

```bash
# conda環境を作成
conda create -n your_conda_name python=3.11
conda activate your_conda_name
```

### 2. 依存関係のインストール

```bash
# 基本依存関係のインストール
pip install -r requirements.txt
# ローカルセンチメント分析モデルを使用したくない場合(計算要件が低く、デフォルトでCPUバージョン)、コマンドを実行する前にこのファイルの「Machine Learning」セクションをコメントアウトできます。
```

### 3. Playwrightブラウザドライバのインストール

```bash
# ブラウザドライバのインストール(クローラー機能用)
playwright install chromium
```

### 4. システム設定

#### 4.1 APIキーの設定

`config.py.example`ファイルを`config.py`にコピー

`config.py`ファイルを編集し、APIキーを入力します(独自のモデルと検索プロキシを選択することもできます。詳細については設定ファイルを参照してください):

```python
# MySQLデータベース設定
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "your_username"
DB_PASSWORD = "your_password"
DB_NAME = "your_db_name"
DB_CHARSET = "utf8mb4"

# LLM設定
# OpenAI互換のリクエスト形式に従う限り、各EngineのLLMプロバイダーを切り替えることができます

# Insight Agent
INSIGHT_ENGINE_API_KEY = "your_api_key"
INSIGHT_ENGINE_BASE_URL = "https://api.moonshot.cn/v1"
INSIGHT_ENGINE_MODEL_NAME = "kimi-k2-0711-preview"
# Media Agent
...
```

#### 4.2 データベースの初期化

**オプション1: ローカルデータベースを使用**

設定テンプレートについては`MindSpider\config.py.example`を参照し、このファイルをコピーして`config.py`に名前を変更できます。

```bash
# ローカルMySQLデータベースの初期化
cd MindSpider
python schema/init_database.py
```

**オプション2: クラウドデータベースサービスを使用(推奨)**

10万以上の日次リアル世論データを備えた便利なクラウドデータベースサービスを提供しており、現在**無料申請中**です!

- リアル世論データ、リアルタイム更新
- 多次元タグ分類
- 高可用性クラウドサービス
- プロフェッショナル技術サポート

**無料クラウドデータベースアクセスの申請についてお問い合わせください: 📧 670939375@qq.com**

> データコンプライアンスレビューとサービスアップグレードを実施するため、2025年10月1日より、クラウドデータベースの新規申請を一時停止しています。

### 5. システムの起動

#### 5.1 完全システムの起動(推奨)

```bash
# プロジェクトルートディレクトリで、conda環境をアクティブ化
conda activate your_conda_name

# メインアプリケーションの起動
python app.py
```

> 注意1: 実行が終了した後、Streamlitアプリが正しくシャットダウンされず、ポートを占有している可能性があります。この場合、ポートを保持しているプロセスを見つけて終了してください。

> 注意2: データスクレイピングは別の操作として実行する必要があります。セクション5.3の手順を参照してください。

> 注意3: リモートサーバーデプロイメント中にページ表示の問題が発生した場合は、[PR#45](https://github.com/666ghj/BettaFish/pull/45)を参照してください。

http://localhost:5000 にアクセスして完全なシステムを使用します

#### 5.2 個別エージェントの起動

```bash
# QueryEngineの起動
streamlit run SingleEngineApp/query_engine_streamlit_app.py --server.port 8503

# MediaEngineの起動
streamlit run SingleEngineApp/media_engine_streamlit_app.py --server.port 8502

# InsightEngineの起動
streamlit run SingleEngineApp/insight_engine_streamlit_app.py --server.port 8501
```

#### 5.3 クローラーシステムのスタンドアロン使用

このセクションには詳細な設定ドキュメントがあります: [MindSpider使用ガイド](./MindSpider/README.md)

<div align="center">
<img src="MindSpider\img\example.png" alt="banner" width="600">

MindSpider実行例
</div>

```bash
# クローラーディレクトリに入る
cd MindSpider

# プロジェクトの初期化
python main.py --setup

# 完全なクローラーワークフローの実行
python main.py --complete --date 2024-01-20

# トピック抽出のみ実行
python main.py --broad-topic --date 2024-01-20

# 詳細クローリングのみ実行
python main.py --deep-sentiment --platforms xhs dy wb
```

## ⚙️ 高度な設定

### 主要パラメータの変更

#### エージェント設定パラメータ

各エージェントには専用の設定ファイルがあり、ニーズに応じて調整できます:

```python
# QueryEngine/utils/config.py
class Config:
    max_reflections = 2           # リフレクションラウンド
    max_search_results = 15       # 最大検索結果
    max_content_length = 8000     # 最大コンテンツ長

# MediaEngine/utils/config.py
class Config:
    comprehensive_search_limit = 10  # 包括的検索制限
    web_search_limit = 15           # Web検索制限

# InsightEngine/utils/config.py
class Config:
    default_search_topic_globally_limit = 200    # グローバル検索制限
    default_get_comments_limit = 500             # コメント取得制限
    max_search_results_for_llm = 50              # LLMの最大結果
```

#### センチメント分析モデル設定

```python
# InsightEngine/tools/sentiment_analyzer.py
SENTIMENT_CONFIG = {
    'model_type': 'multilingual',     # オプション: 'bert', 'multilingual', 'qwen'
    'confidence_threshold': 0.8,      # 信頼度しきい値
    'batch_size': 32,                 # バッチサイズ
    'max_sequence_length': 512,       # 最大シーケンス長
}
```

### 異なるLLMモデルの統合

システムは、OpenAIリクエスト形式に従う任意のLLMプロバイダーをサポートします。`config.py`でKEY、BASE_URL、MODEL_NAMEを入力するだけです。

> OpenAIリクエスト形式とは何ですか?簡単な例を示します:
>```python
>from openai import OpenAI
>
>client = OpenAI(api_key="your_api_key",
>                base_url="https://api.siliconflow.cn/v1")
>
>response = client.chat.completions.create(
>    model="Qwen/Qwen2.5-72B-Instruct",
>    messages=[
>        {
>            'role': 'user',
>            'content': "推論モデルは市場にどのような新しい機会をもたらしますか?"
>        }
>    ],
>)
>
>complete_response = response.choices[0].message.content
>print(complete_response)
>```

### センチメント分析モデルの変更

システムは複数のセンチメント分析方法を統合しており、ニーズに基づいて選択できます:

#### 1. 多言語センチメント分析

```bash
cd SentimentAnalysisModel/WeiboMultilingualSentiment
python predict.py --text "この製品は素晴らしいです!" --lang "ja"
```

#### 2. 小パラメータQwen3微調整

```bash
cd SentimentAnalysisModel/WeiboSentiment_SmallQwen
python predict_universal.py --text "このイベントは非常に成功しました"
```

#### 3. BERTベースの微調整モデル

```bash
# BERT中国語モデルを使用
cd SentimentAnalysisModel/WeiboSentiment_Finetuned/BertChinese-Lora
python predict.py --text "この製品は本当に素晴らしい"
```

#### 4. GPT-2 LoRA微調整モデル

```bash
cd SentimentAnalysisModel/WeiboSentiment_Finetuned/GPT2-Lora
python predict.py --text "今日はあまり気分が良くない"
```

#### 5. 従来の機械学習手法

```bash
cd SentimentAnalysisModel/WeiboSentiment_MachineLearning
python predict.py --model_type "svm" --text "サービス態度の改善が必要"
```

### カスタムビジネスデータベースの統合

#### 1. データベース接続設定の変更

```python
# config.pyにビジネスデータベース設定を追加
BUSINESS_DB_HOST = "your_business_db_host"
BUSINESS_DB_PORT = 3306
BUSINESS_DB_USER = "your_business_user"
BUSINESS_DB_PASSWORD = "your_business_password"
BUSINESS_DB_NAME = "your_business_database"
```

#### 2. カスタムデータアクセスツールの作成

```python
# InsightEngine/tools/custom_db_tool.py
class CustomBusinessDBTool:
    """カスタムビジネスデータベースクエリツール"""

    def __init__(self):
        self.connection_config = {
            'host': config.BUSINESS_DB_HOST,
            'port': config.BUSINESS_DB_PORT,
            'user': config.BUSINESS_DB_USER,
            'password': config.BUSINESS_DB_PASSWORD,
            'database': config.BUSINESS_DB_NAME,
        }

    def search_business_data(self, query: str, table: str):
        """ビジネスデータのクエリ"""
        # ビジネスロジックを実装
        pass

    def get_customer_feedback(self, product_id: str):
        """顧客フィードバックデータの取得"""
        # 顧客フィードバッククエリロジックを実装
        pass
```

#### 3. InsightEngineへの統合

```python
# InsightEngine/agent.pyでカスタムツールを統合
from .tools.custom_db_tool import CustomBusinessDBTool

class DeepSearchAgent:
    def __init__(self, config=None):
        # ... その他の初期化コード
        self.custom_db_tool = CustomBusinessDBTool()

    def execute_custom_search(self, query: str):
        """カスタムビジネスデータ検索の実行"""
        return self.custom_db_tool.search_business_data(query, "your_table")
```

### カスタムレポートテンプレート

#### 1. Webインターフェースでアップロード

システムは、カスタムテンプレートファイル(.mdまたは.txt形式)のアップロードをサポートしており、レポート生成時に選択できます。

#### 2. テンプレートファイルの作成

`ReportEngine/report_template/`ディレクトリに新しいテンプレートを作成すると、エージェントが自動的に最も適切なテンプレートを選択します。

## 🤝 貢献ガイド

あらゆる形式の貢献を歓迎します!

### 貢献方法

1. プロジェクトをGitHubアカウントに**フォーク**
2. **Featureブランチを作成**: `git checkout -b feature/AmazingFeature`
3. **変更をコミット**: `git commit -m 'Add some AmazingFeature'`
4. **ブランチにプッシュ**: `git push origin feature/AmazingFeature`
5. **Pull Requestを開く**

### 開発基準

- コードはPEP8標準に従う
- コミットメッセージは明確な日本語/英語の説明を使用
- 新機能には対応するテストケースが必要
- 関連ドキュメントを更新

## 🦖 次の開発計画

システムは現在、「3ステップアプローチ」の最初の2ステップのみを完了しています: 要件入力 -> 詳細分析。欠落しているステップは予測であり、これをLLMに直接渡すことは説得力に欠けます。

<div align="center">
<img src="static/image/banner_compressed.png" alt="banner" width="800">
</div>

現在、長期間のクローリングと収集の後、トピックの人気トレンドの経時変化、トレンドイベント、その他のネットワーク全体の変化パターンに関する大量のデータを蓄積しています。予測モデルを開発する条件が整っています。チームは、時系列モデル、グラフニューラルネットワーク、マルチモーダル融合、その他の予測モデル技術の技術的蓄積を適用して、真にデータ駆動型の世論予測機能を実現します。

## ⚠️ 免責事項

**重要なお知らせ: このプロジェクトは教育、学術研究、学習目的のみを対象としています**

1. **コンプライアンス声明**:
   - このプロジェクトのすべてのコード、ツール、機能は、教育、学術研究、学習目的のみを対象としています
   - 商業利用または利益を得る活動は厳しく禁止されています
   - 違法、非準拠、または権利侵害活動は厳しく禁止されています

2. **Webスクレイピング免責事項**:
   - このプロジェクトのWebスクレイピング機能は、技術学習と研究目的のみを対象としています
   - ユーザーは、対象Webサイトのrobots.txtプロトコルと利用規約を遵守する必要があります
   - ユーザーは、関連する法律と規制を遵守し、悪意のあるスクレイピングやデータの悪用を行ってはなりません
   - Webスクレイピング機能の使用から生じる法的結果については、ユーザーが単独で責任を負います

3. **データ使用免責事項**:
   - このプロジェクトのデータ分析機能は、学術研究目的のみを対象としています
   - 商業的意思決定または利益を得る目的で分析結果を使用することは厳しく禁止されています
   - ユーザーは、分析対象データの合法性とコンプライアンスを確保する必要があります

4. **技術免責事項**:
   - このプロジェクトは、明示的または暗黙的な保証なしに「現状のまま」提供されます
   - 著者は、このプロジェクトの使用によって引き起こされる直接的または間接的な損失について責任を負いません
   - ユーザーは、このプロジェクトの適用性とリスクを独立して評価する必要があります

5. **責任制限**:
   - このプロジェクトを使用する前に、ユーザーは関連する法律と規制を完全に理解する必要があります
   - ユーザーは、使用が地域の法的および規制要件に準拠していることを確認する必要があります
   - このプロジェクトの違法使用から生じる結果については、ユーザーが単独で責任を負います

**このプロジェクトを使用する前に、上記の免責事項を注意深く読んで理解してください。このプロジェクトを使用することは、上記のすべての条件に同意し、受け入れたことを示します。**

## 📄 ライセンス

このプロジェクトは[GPL-2.0ライセンス](LICENSE)の下でライセンスされています。詳細については、LICENSEファイルを参照してください。

## 🎉 サポート & お問い合わせ

### ヘルプの取得

- **プロジェクトホームページ**: [GitHubリポジトリ](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem)
- **問題報告**: [Issuesページ](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem/issues)
- **機能リクエスト**: [Discussionsページ](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem/discussions)

### 連絡先情報

- 📧 **メール**: 670939375@qq.com

### ビジネス協力

- **エンタープライズカスタム開発**
- **ビッグデータサービス**
- **学術協力**
- **技術トレーニング**

## 👥 貢献者

これらの優れた貢献者に感謝します:

[![Contributors](https://contrib.rocks/image?repo=666ghj/Weibo_PublicOpinion_AnalysisSystem)](https://github.com/666ghj/Weibo_PublicOpinion_AnalysisSystem/graphs/contributors)

## 📈 プロジェクト統計

<a href="https://www.star-history.com/#666ghj/BettaFish&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=666ghj/BettaFish&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=666ghj/BettaFish&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=666ghj/BettaFish&type=date&legend=top-left" />
 </picture>
</a>

![Alt](https://repobeats.axiom.co/api/embed/e04e3eea4674edc39c148a7845c8d09c1b7b1922.svg "Repobeats analytics image")
