# 土壌検査変換ツール（パスワード保護版）

Streamlit Community Cloud 用です。

## Streamlit設定
- Branch: `main`
- Main file path: `app.py`

## 重要：サインイン不要で共有する設定

Streamlitのアプリ自体を **Public** にして、
アプリ内部のパスワード画面で閲覧を制限します。

### 1. Streamlit Secrets にパスワードを設定
App settings → Secrets に以下を入力します。

```toml
APP_PASSWORD = "ここに好きなパスワード"
```

パスワードはGitHubのコードに書かないでください。

### 2. StreamlitのSharing設定
Who can view this app を **Public** にします。

これで相手はStreamlitへのサインインなしでURLを開けますが、
アプリの内容を見るには設定したパスワードが必要です。

## パスワード変更
Streamlitの App settings → Secrets で APP_PASSWORD を変更して保存します。
GitHubのコード修正は不要です。


## v7 一軸圧縮対応

コンシステンシー（W:Z）と三軸圧縮の間に一軸圧縮を追加しました。

- 上段見出し：`一軸圧縮`
- 下段見出し：`一軸圧縮強さqu (kN/m)`
- データ列：3列（同一採取深度で最大3回の試験値を記載可能）
- 既存の三軸圧縮・Pc・Ccは右へ移動します。
