"""
YouTube 4K 视频下载器
使用 customtkinter 创建现代化界面，yt_dlp 处理下载逻辑
"""

import customtkinter as ctk
import yt_dlp
import threading
import os
import shutil
from tkinter import messagebox

# 👇👇👇 在这里插入 👇👇👇
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"

# 设置 customtkinter 外观
ctk.set_appearance_mode("System")  # 系统模式（自动跟随系统深色/浅色）
ctk.set_default_color_theme("blue")  # 蓝色主题


class YouTubeDownloader(ctk.CTk):
    """YouTube 下载器主窗口类"""
    
    def __init__(self):
        super().__init__()
        
        # 窗口基本配置
        self.title("4K 视频下载神器")
        self.geometry("700x520")
        # self.resizable(False, False) # 允许调整大小体验更好
        
        # 初始化 UI
        self.setup_ui()
        
        # 下载状态标志
        self.is_downloading = False
        
    def setup_ui(self):
        """设置用户界面"""
        
        # 配置 grid 布局权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 主容器（带内边距）
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        
        # 标题标签
        title_label = ctk.CTkLabel(
            main_frame,
            text="🎬 4K 视频下载神器",
            font=ctk.CTkFont(size=26, weight="bold")
        )
        title_label.pack(pady=(0, 25))
        
        # URL 输入框
        url_label = ctk.CTkLabel(main_frame, text="视频链接：", font=ctk.CTkFont(size=14))
        url_label.pack(anchor="w", pady=(5, 5))
        
        self.url_entry = ctk.CTkEntry(
            main_frame,
            placeholder_text="请在此粘贴 YouTube 链接",
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.url_entry.pack(fill="x", pady=(0, 15))
        
        # 画质选择下拉框
        quality_label = ctk.CTkLabel(main_frame, text="视频画质：", font=ctk.CTkFont(size=14))
        quality_label.pack(anchor="w", pady=(5, 5))
        
        self.quality_combo = ctk.CTkComboBox(
            main_frame,
            values=["最高画质 (4K/8K)", "1080p", "720p", "仅音频"],
            state="readonly",
            height=35,
            font=ctk.CTkFont(size=13)
        )
        self.quality_combo.set("最高画质 (4K/8K)")  # 默认选择
        self.quality_combo.pack(fill="x", pady=(0, 15))
        
        # 字幕选项复选框
        self.subtitle_checkbox = ctk.CTkCheckBox(
            main_frame,
            text="下载字幕 (包含中文/英文)",
            font=ctk.CTkFont(size=13)
        )
        self.subtitle_checkbox.pack(anchor="w", pady=(5, 20))
        
        # 下载按钮
        self.download_btn = ctk.CTkButton(
            main_frame,
            text="开始下载",
            command=self.start_download,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            corner_radius=10
        )
        self.download_btn.pack(fill="x", pady=(10, 20))
        
        # 进度/日志文本框
        log_label = ctk.CTkLabel(main_frame, text="实时日志/进度：", font=ctk.CTkFont(size=14))
        log_label.pack(anchor="w", pady=(5, 5))
        
        self.log_textbox = ctk.CTkTextbox(
            main_frame,
            height=120,
            font=ctk.CTkFont(size=12, family="Consolas"), # 使用等宽字体显示日志更好看
            wrap="word"
        )
        self.log_textbox.pack(fill="both", expand=True)
        self.log_textbox.insert("1.0", "等待任务...\n")
        self.log_textbox.configure(state="disabled")  # 设为只读
        
    def log_message(self, message):
        """
        在日志框中显示消息 (线程安全)
        使用 self.after 确保 UI更新 在主线程执行
        """
        def _update():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", f"{message}\n")
            self.log_textbox.see("end")  # 自动滚动到底部
            self.log_textbox.configure(state="disabled")
        
        self.after(0, _update)

    def set_downloading_state(self, is_downloading):
        """设置界面下载状态 (线程安全)"""
        def _update():
            self.is_downloading = is_downloading
            if is_downloading:
                self.download_btn.configure(state="disabled", text="正在下载中...")
                self.url_entry.configure(state="disabled")
                self.quality_combo.configure(state="disabled")
                self.subtitle_checkbox.configure(state="disabled")
            else:
                self.download_btn.configure(state="normal", text="开始下载")
                self.url_entry.configure(state="normal")
                self.quality_combo.configure(state="normal")
                self.subtitle_checkbox.configure(state="normal")
        
        self.after(0, _update)

    def start_download(self):
        """点击开始下载按钮触发"""
        
        # 防止重复点击
        if self.is_downloading:
            return
        
        # 获取 URL
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入有效的 YouTube 链接！")
            return
        
        # 清空日志
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self.log_message(f"🚀 准备下载: {url}")
        
        # 设置状态为下载中
        self.set_downloading_state(True)
        
        # 在新线程中执行下载，防止界面卡顿
        download_thread = threading.Thread(
            target=self.download_video_thread,
            args=(url,),
            daemon=True
        )
        download_thread.start()
        
    def download_video_thread(self, url):
        """后台下载线程逻辑"""
        
        try:
            # 获取用户选择的画质
            quality_choice = self.quality_combo.get()
            
            # 根据用户选择配置 yt-dlp format 字符串
            if quality_choice == "最高画质 (4K/8K)":
                # 下载最佳视频+最佳音频，如果不行则下载最佳单一文件
                format_str = "bestvideo+bestaudio/best"
            elif quality_choice == "1080p":
                format_str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best[height<=1080]"
            elif quality_choice == "720p":
                format_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=720]"
            else:  # "仅音频"
                format_str = "bestaudio/best"
            
            # 检查 ffmpeg 是否在当前目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_exe = os.path.join(current_dir, "ffmpeg.exe")
            
            ffmpeg_location = None
            if os.path.exists(ffmpeg_exe):
                ffmpeg_location = current_dir
                self.log_message("🔧 检测到本地 ffmpeg.exe")
            elif shutil.which("ffmpeg"): # 检查系统环境变量
                self.log_message("🔧 检测到系统路径 ffmpeg")
            else:
                self.log_message("⚠️ 未找到 ffmpeg，合并视频可能会失败 (建议将 ffmpeg.exe 放入同级目录)")

            # 配置 yt_dlp 选项
            ydl_opts = {
                'format': format_str,
                'merge_output_format': 'mp4',  # 只有视频需要合并，音频通常不影响，或者会自动处理
                'outtmpl': os.path.join(current_dir, '%(title)s.%(ext)s'),  # 保存到当前目录
                'progress_hooks': [self.progress_hook],  # 进度回调
                # 'quiet': True, # 如果想减少控制台输出可以开启
                'no_warnings': True,
                'proxy': 'http://127.0.0.1:7890',  # 配置本地代理解决连接问题
            }

            if ffmpeg_location:
                ydl_opts['ffmpeg_location'] = ffmpeg_location

            # 如果选择仅音频，可能不需要合并为 mp4，但用户要求 "merge-output-format mp4" 是在 "最高画质" 上下文。
            # 为了安全起见，如果是音频，我们通常希望是 mp3/m4a。
            # 这里按照用户"最高画质"的逻辑合并 mp4，如果是音频，保持默认或转换为常见格式更好。
            # 简单起见，严格遵循用户对 "最高画质" 的 merge 要求，对音频不做强制 mp4 转换以免怪异，除非 yt-dlp 自动处理。
            
            # 如果选择下载字幕
            # 逻辑要求: 'writesubtitles': True, 'subtitleslangs': ['en', 'zh-Hans']
            if self.subtitle_checkbox.get():
                ydl_opts['writesubtitles'] = True
                ydl_opts['subtitleslangs'] = ['en', 'zh-Hans', 'zh-CN', 'zh-Hant'] # 添加更多中文变体以防万一
                # ydl_opts['subtitlesformat'] = 'srt/best' # 可选
                self.log_message("📝 已启用字幕下载")
            
            self.log_message(f"⚙️ 画质配置: {quality_choice}")
            self.log_message("⏳ 正在解析视频元数据...")
            
            # 开始下载
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_title = info.get('title', 'Unknown Title')
                self.log_message(f"✅ 下载完成: {video_title}")
                
            # 弹出成功提示 (需要在主线程)
            self.after(0, lambda: messagebox.showinfo("成功", "🎉 视频下载成功！"))
            
        except Exception as e:
            error_msg = str(e)
            self.log_message(f"❌ 发生错误: {error_msg}")
            self.after(0, lambda: messagebox.showerror("下载失败", f"错误详情:\n{error_msg}"))
            
        finally:
            # 无论成功失败，最后都恢复界面状态
            self.set_downloading_state(False)
    
    def progress_hook(self, d):
        """yt_dlp 进度回调函数"""
        # 注意: 此函数是在后台线程被调用的
        
        if d['status'] == 'downloading':
            # 移除 ANSI 颜色代码 (如果 shell 输出包含)
            percent = d.get('_percent_str', '').replace('\x1b[0;94m', '').replace('\x1b[0m', '')
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            
            msg = f"⬇️ 下载中... {percent} | 速度: {speed} | 剩余: {eta}"
            # 为了不刷屏太快，可以只显示最后一行（但 Textbox update 较快，直接 append 也可以，主要看用户体验）
            # 这里我们直接 append，用户可以看到历史记录
            # 稍微优化：如果上一行也是进度，可以考虑替换，但简单 append 实现最稳定
            self.log_message(msg)
            
        elif d['status'] == 'finished':
            self.log_message("� 下载分片完成，正在合并/转换...")

def main():
    app = YouTubeDownloader()
    app.mainloop()

if __name__ == "__main__":
    main()
