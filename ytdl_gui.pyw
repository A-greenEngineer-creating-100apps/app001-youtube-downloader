# -*- coding: utf-8 -*-
"""
YouTube ダウンローダ (GUI版・トグル式)
-------------------------------------------------
特徴:
- 常に表示されるメインウィンドウ（消えない）
- URL入力欄、保存先フォルダ選択、MP3/MP4トグルスイッチ風切替
- 進行状況ログ表示
- ダウンロードは別スレッドで実行（UIが固まらない）

準備:
1) pip install yt-dlp
2) ffmpeg をインストールして PATH に追加（MP3 変換/動画結合に必須）

※ 利用は各プラットフォームの規約・法律に従ってください。
"""
import os
import threading
import queue
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# 依存チェック
missing = []
try:
    import yt_dlp  # type: ignore
except Exception:
    missing.append("yt-dlp")
if shutil.which("ffmpeg") is None:
    missing.append("ffmpeg")
if missing:
    msg = "以下が見つかりませんでした:\n- " + "\n- ".join(missing) + \
          "\n\n対処:\n  pip install yt-dlp\n  ffmpeg をインストールして PATH に追加\n\nアプリは起動しますが、ダウンロード時に失敗します。"
    print(msg)

# ---------- スイッチ風トグル（Canvasベース） ----------
class ToggleSwitch(ttk.Frame):
    """
    BooleanVar と連動するスイッチ風ウィジェット。
    True/False を on_text/off_text で表示。command は切替時に呼ばれる。
    """
    def __init__(self, master, variable: tk.BooleanVar, on_text="ON", off_text="OFF",
                 width=110, height=36, command=None):
        super().__init__(master)
        self.var = variable
        self.on_text = on_text
        self.off_text = off_text
        self.command = command

        self.width = width
        self.height = height
        self.radius = height // 2

        self.canvas = tk.Canvas(self, width=width, height=height, highlightthickness=0, bg=self._bg())
        self.canvas.pack()

        # マウス操作
        self.canvas.bind("<Button-1>", self._toggle)
        self.canvas.bind("<space>", self._toggle)
        self.canvas.bind("<Return>", self._toggle)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.configure(cursor="hand2")
        self.canvas.focus_set()

        # 変数の変化を監視して描画を更新
        self.var.trace_add("write", lambda *args: self._redraw())

        self._redraw()

    def _bg(self):
        # 親の背景色を継承（見た目の一体感）
        try:
            return self.master.cget("background")
        except Exception:
            return "SystemButtonFace"

    def _toggle(self, event=None):
        self.var.set(not self.var.get())
        self._redraw()
        if self.command:
            self.command()

    def _redraw(self):
        self.canvas.delete("all")
        w, h, r = self.width, self.height, self.radius
        on = self.var.get()

        # ベース（丸角長方形）
        x0, y0, x1, y1 = 2, 2, w-2, h-2
        track_color = "#34c759" if on else "#999999"     # 緑/グレー
        knob_color = "#ffffff"

        # 丸角を描く
        self.canvas.create_round_rect = getattr(self.canvas, "create_round_rect", None)
        if not self.canvas.create_round_rect:
            # ない環境向けシンプル描画（左右の円＋中央矩形）
            self.canvas.create_oval(x0, y0, y0*1 + h-4, y1, fill=track_color, outline=track_color)
            self.canvas.create_oval(x1-(h-4), y0, x1, y1, fill=track_color, outline=track_color)
            self.canvas.create_rectangle(x0 + (h-4)//2, y0, x1 - (h-4)//2, y1, fill=track_color, outline=track_color)
        else:
            self.canvas.create_round_rect(x0, y0, x1, y1, radius=r-2, fill=track_color, outline=track_color)

        # ノブ位置
        pad = 3
        knob_d = h - pad*2
        knob_x = x1 - pad - knob_d if on else x0 + pad
        self.canvas.create_oval(knob_x, pad, knob_x + knob_d, pad + knob_d, fill=knob_color, outline="#dddddd")

        # ラベル
        label = f"{self.on_text if on else self.off_text}"
        self.canvas.create_text(w//2, h//2, text=label, fill="white", font=("Meiryo UI", 10, "bold"))

# ---------------- GUI ----------------
class YtDlGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube ダウンローダ")
        self.geometry("640x420")
        self.minsize(620, 400)

        # 変数
        self.url_var = tk.StringVar()
        self.save_dir_var = tk.StringVar()
        self.as_mp3_var = tk.BooleanVar(value=True)  # True=MP3, False=MP4

        # ログ用
        self.log_queue = queue.Queue()
        self.is_downloading = False
        self.worker_thread = None

        self._build_widgets()
        self._poll_log_queue()

    def _build_widgets(self):
        pad = {"padx": 12, "pady": 8}

        # URL
        frm_url = ttk.LabelFrame(self, text="URL")
        frm_url.pack(fill="x", **pad)
        ttk.Entry(frm_url, textvariable=self.url_var).pack(side="left", fill="x", expand=True, padx=8, pady=8)
        ttk.Button(frm_url, text="貼り付け", command=self._paste_from_clipboard).pack(side="left", padx=8, pady=8)

        # 保存先
        frm_save = ttk.LabelFrame(self, text="保存先フォルダ")
        frm_save.pack(fill="x", **pad)
        save_row = ttk.Frame(frm_save)
        save_row.pack(fill="x", padx=8, pady=8)
        self.save_dir_entry = ttk.Entry(save_row, textvariable=self.save_dir_var)
        self.save_dir_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(save_row, text="参照...", command=self._choose_dir).pack(side="left", padx=8)

        # 形式（スイッチ風トグル）
        frm_fmt = ttk.LabelFrame(self, text="形式")
        frm_fmt.pack(fill="x", **pad)
        fmt_row = ttk.Frame(frm_fmt)
        fmt_row.pack(fill="x", padx=8, pady=8)

        self.switch = ToggleSwitch(
            fmt_row,
            variable=self.as_mp3_var,
            on_text="MP3（音声）",
            off_text="MP4（動画）",
            width=180,
            height=36,
            command=self._on_toggle_changed
        )
        self.switch.pack(side="left")

        # 実行ボタン
        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", **pad)
        self.run_btn = ttk.Button(btn_row, text="ダウンロード開始", command=self._on_run_clicked)
        self.run_btn.pack(side="left", padx=8)
        self.cancel_btn = ttk.Button(btn_row, text="キャンセル", command=self._on_cancel_clicked, state="disabled")
        self.cancel_btn.pack(side="left")

        # ログ
        frm_log = ttk.LabelFrame(self, text="ログ")
        frm_log.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(frm_log, height=10, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)
        self._log("準備OK：URL と 保存先 を指定して、形式を切り替えてください。")

        # 既定保存先
        try:
            from pathlib import Path
            default_dl = str(Path.home() / "Downloads")
            if os.path.isdir(default_dl):
                self.save_dir_var.set(default_dl)
        except Exception:
            pass

    def _on_toggle_changed(self):
        # スイッチ表示はToggleSwitch側で更新済み。ここではログだけ。
        self._log(f"形式を切替: {'MP3(音声)' if self.as_mp3_var.get() else 'MP4(動画)'}")

    def _paste_from_clipboard(self):
        try:
            self.url_var.set(self.clipboard_get())
        except Exception:
            pass

    def _choose_dir(self):
        d = filedialog.askdirectory(title="保存先フォルダを選んでください", initialdir=self.save_dir_var.get() or None)
        if d:
            self.save_dir_var.set(d)

    def _on_run_clicked(self):
        if self.is_downloading:
            return
        url = (self.url_var.get() or "").strip()
        save_dir = (self.save_dir_var.get() or "").strip()
        if not url:
            messagebox.showwarning("入力不足", "URL を入力してください。")
            return
        if not save_dir or not os.path.isdir(save_dir):
            messagebox.showwarning("入力不足", "保存先フォルダを正しく指定してください。")
            return

        # 依存チェック（実行時）
        try:
            import yt_dlp  # noqa: F401
        except Exception:
            messagebox.showerror("エラー", "yt-dlp が見つかりません。\n\npip install yt-dlp を実行してください。")
            return
        if shutil.which("ffmpeg") is None:
            messagebox.showerror("エラー", "ffmpeg が見つかりません。\n\nffmpeg をインストールして PATH に追加してください。")
            return

        self.is_downloading = True
        self.run_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self._log("ダウンロードを開始します…")

        self.worker_thread = threading.Thread(
            target=self._do_download, args=(url, save_dir, self.as_mp3_var.get()), daemon=True
        )
        self.worker_thread.start()

    def _on_cancel_clicked(self):
        self._log("キャンセル要求を受け付けました。しばらくお待ちください…（現在の処理単位が終わるまで継続する可能性があります）")
        self.is_downloading = False

    def _poll_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self._append_log_line(line)
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _append_log_line(self, text):
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")

    def _log(self, text):
        self.log_queue.put(text)

    def _do_download(self, url: str, save_dir: str, as_mp3: bool):
        try:
            import yt_dlp

            outtmpl = os.path.join(save_dir, "%(title)s [%(id)s].%(ext)s")
            ydl_opts = {
                "outtmpl": outtmpl,
                "noprogress": True,
                "quiet": True,
                "windowsfilenames": True,
            }

            if as_mp3:
                ydl_opts.update({
                    "format": "bestaudio/best",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                })
            else:
                ydl_opts.update({
                    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "merge_output_format": "mp4",
                })

            class Logger:
                def debug(self, msg):
                    if msg and not msg.startswith("[debug]"):
                        self._emit(msg)
                def warning(self, msg): self._emit(msg)
                def error(self, msg): self._emit(msg)
                def _emit(self, msg):
                    self_outer._log(msg)

            self_outer = self
            ydl_opts["logger"] = Logger()

            def hook(d):
                if d.get("status") == "downloading":
                    eta = d.get("eta")
                    speed = d.get("speed")
                    p = d.get("downloaded_bytes", 0)
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    if total:
                        percent = p * 100.0 / total
                        self_outer._log(f"進行中: {percent:5.1f}% | 速度: {speed or 0:.0f} B/s | 残り: {eta or 0}s")
                elif d.get("status") == "finished":
                    self_outer._log("変換/結合中…")

            ydl_opts["progress_hooks"] = [hook]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            base = f"{info.get('title','download')} [{info.get('id','id')}]." + ("mp3" if as_mp3 else "mp4")
            saved_path = os.path.join(save_dir, base)

            if os.path.exists(saved_path):
                self._log("完了: " + saved_path)
                try:
                    os.startfile(saved_path)  # Windows
                except Exception:
                    pass
            else:
                self._log("完了（注意：ファイル名が異なる可能性あり）。保存先フォルダを開きます。")
                try:
                    os.startfile(save_dir)
                except Exception:
                    pass

        except Exception as e:
            self._log(f"エラー: {e}")
            messagebox.showerror("エラー", f"ダウンロードでエラーが発生しました:\n{e}")
        finally:
            self.is_downloading = False
            self.run_btn.config(state="normal")
            self.cancel_btn.config(state="disabled")
            self._log("待機中。別のURLで続けられます。")

if __name__ == "__main__":
    app = YtDlGUI()
    app.mainloop()