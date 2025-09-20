# app001-youtube-downloader
100 Apps Challenge #001 - YouTube Downloader (Python, learning purpose)
---

## 📖 概要
Python と Tkinter で作成したシンプルな **YouTube ダウンローダー** です。  
URLを入力して保存先を選び、MP3（音声）か MP4（動画）をスイッチで切り替えてダウンロードできます。  
学習・検証を目的としたサンプルであり、各サービスの利用規約・法律を遵守してご利用ください。

---

必要環境
- Python 3.9 以上  
- 依存ライブラリ: [yt-dlp](https://github.com/yt-dlp/yt-dlp)  
- 外部ツール: [ffmpeg](https://ffmpeg.org/) （MP3変換や動画結合に必須）

---

セットアップ
1. このリポジトリをクローン or ZIPダウンロード  
2. 必要ライブラリをインストール
   ```bash
   pip install -r requirements.txt
ffmpeg をインストールして、PATHを通す
（Windowsなら ffmpeg builds など）

---

▶️ 使い方
<img width="650" height="454" alt="image" src="https://github.com/user-attachments/assets/5603c417-5e88-40c2-9de9-ce670a0847f9" />
URL欄に YouTube の動画URLを入力
保存先フォルダを指定
スイッチを切り替えて MP3 / MP4 を選択
「ダウンロード開始」を押すと保存されます

---

📚 学び（備忘録）
Tkinter での UI 構築（フレーム構成、スイッチUIの自作）
yt-dlp を Python から利用して動画/音声を処理
スレッドを使って UI を固まらせない工夫

