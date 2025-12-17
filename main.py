"""
YouTube 4K 视频下载器 (升级版)
功能：
1. 支持播放列表解析与选择下载 (前 20-50 个视频)
2. 支持暂停/继续下载
3. 现代化深色 UI
"""

import os
import sys # Added for Frozen Path Fix
# 👇👇👇 必须保留的代理配置 👇👇👇
#os.environ["http_proxy"] = "http://127.0.0.1:7890"
#os.environ["https_proxy"] = "http://127.0.0.1:7890"

import customtkinter as ctk
import yt_dlp
import threading
import shutil
import time
from tkinter import messagebox

# 设置 customtkinter 外观
ctk.set_appearance_mode("System")  # 系统模式
ctk.set_default_color_theme("blue")  # 蓝色主题

class PauseException(Exception):
    """用于暂停下载的自定义异常"""
    pass

def get_app_path():
    """Returns the actual path of the executable (if frozen) or the script."""
    if getattr(sys, 'frozen', False):
        # If running as compiled .exe
        return os.path.dirname(sys.executable)
    else:
        # If running as standard .py script
        return os.path.dirname(os.path.abspath(__file__))

class YouTubeDownloader(ctk.CTk):
    """YouTube 下载器主窗口类"""
    
    def __init__(self):
        super().__init__()
        
        # 窗口基本配置
        self.title("Universal Video Downloader (YouTube & Bilibili)")
        self.geometry("700x600")
        
        # 状态控制变量
        self.stop_event = threading.Event() # 用于控制暂停
        self.is_downloading = False
        self.is_paused = False
        self.current_download_urls = [] # 当前待下载的 URL 列表
        self.current_app_state = "idle" # idle, downloading, paused
        
        # 初始化 UI
        self.setup_ui()
        
    def setup_ui(self):
        """设置用户界面"""
        
        # 配置 grid 布局权重
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 主容器
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        
        # 标题
        title_label = ctk.CTkLabel(
            main_frame,
            text="🎬 Universal Video Downloader",
            font=ctk.CTkFont(size=26, weight="bold")
        )
        title_label.pack(pady=(0, 20))
        
        # URL 输入框
        url_label = ctk.CTkLabel(main_frame, text="视频/播放列表链接：", font=ctk.CTkFont(size=14))
        url_label.pack(anchor="w", pady=(5, 5))
        
        self.url_entry = ctk.CTkEntry(
            main_frame,
            placeholder_text="请在此粘贴 YouTube 链接 (支持播放列表)",
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.url_entry.pack(fill="x", pady=(0, 15))
        
        # 画质选择
        quality_label = ctk.CTkLabel(main_frame, text="视频画质：", font=ctk.CTkFont(size=14))
        quality_label.pack(anchor="w", pady=(5, 5))
        
        self.quality_combo = ctk.CTkComboBox(
            main_frame,
            values=["最高画质 (4K/8K)", "1080p", "720p", "仅音频"],
            state="readonly",
            height=35,
            font=ctk.CTkFont(size=13)
        )
        self.quality_combo.set("最高画质 (4K/8K)")
        self.quality_combo.pack(fill="x", pady=(0, 15))
        
        # 字幕选项
        subtitle_label = ctk.CTkLabel(main_frame, text="字幕设置：", font=ctk.CTkFont(size=14))
        subtitle_label.pack(anchor="w", pady=(5, 5))

        self.subtitle_menu = ctk.CTkOptionMenu(
            main_frame,
            values=['不下载 (None)', '中文 (Chinese)', '英语 (English)', '日语 (Japanese)', '所有 (All)'],
            font=ctk.CTkFont(size=13)
        )
        self.subtitle_menu.set('不下载 (None)')
        self.subtitle_menu.pack(fill="x", pady=(0, 20))

        # 网络设置 (IPv6)
        self.ipv6_switch = ctk.CTkSwitch(
            main_frame,
            text="IPv6 优先 (IPv6 Only)",
            font=ctk.CTkFont(size=13)
        )
        self.ipv6_switch.pack(anchor="w", pady=(0, 20))
        
        # --- 底部按钮区域 (Footer) ---
        # 关键修改：先 Pack 底部容器，确保它固定在底部
        self.footer_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.footer_frame.pack(side="bottom", fill="x", pady=(10, 0))

        # 解析/下载按钮 (默认显示)
        self.parse_btn = ctk.CTkButton(
            self.footer_frame,
            text="解析并下载",
            command=self.on_parse_click,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            corner_radius=10
        )
        self.parse_btn.pack(fill="x")

        # 暂停/继续 按钮 (默认隐藏)
        self.pause_btn = ctk.CTkButton(
            self.footer_frame,
            text="⏸️ 暂停下载",
            command=self.pause_download,
            fg_color="#D35400", hover_color="#A04000",
            height=40
        )
        # self.pause_btn.pack(...) managed by set_ui_state

        self.resume_btn = ctk.CTkButton(
            self.footer_frame,
            text="▶️ 继续下载",
            command=self.resume_download,
            fg_color="#27AE60", hover_color="#1E8449",
            state="disabled",
            height=40
        )
        # self.resume_btn.pack(...) managed by set_ui_state

        # 打开文件夹按钮
        self.open_dir_btn = ctk.CTkButton(
            self.footer_frame,
            text="📂 打开下载位置 (Open Folder)",
            command=lambda: os.startfile(get_app_path()),
            height=35,
            fg_color="#5D6D7E", hover_color="#34495E"
        )
        self.open_dir_btn.pack(fill="x", pady=(5, 0))

        # --- 日志区域 (填充剩余空间) ---
        log_label = ctk.CTkLabel(main_frame, text="实时日志/进度：", font=ctk.CTkFont(size=14))
        log_label.pack(anchor="w", pady=(5, 5))
        
        self.log_textbox = ctk.CTkTextbox(
            main_frame,
            height=150,
            font=ctk.CTkFont(size=12, family="Consolas"),
            wrap="word"
        )
        self.log_textbox.pack(fill="both", expand=True)
        self.log_textbox.insert("1.0", "等待任务...\n")
        self.log_textbox.configure(state="disabled")

    def log_message(self, message):
        """线程安全的日志记录"""
        def _update():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", f"{message}\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
        self.after(0, _update)

    def on_parse_click(self):
        """点击解析按钮"""
        if self.is_downloading:
            return
            
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入有效的 YouTube 链接！")
            return
            
        # 清空日志
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        
        # 检查是否为列表
        if "list=" in url:
            self.log_message("📋 检测到播放列表，正在解析 (限前 50 个视频)...")
            self.set_ui_state(processing=True)
            # 开启线程解析
            threading.Thread(target=self.parse_playlist_thread, args=(url,), daemon=True).start()
        else:
            self.log_message("🎥 检测到单视频，准备下载...")
            self.current_download_urls = [url]
            self.start_download_process()

    def parse_playlist_thread(self, url):
        """解析播放列表 (后台线程)"""
        ydl_opts = {
            'extract_flat': True,  # 只获取元数据，不下载
            'playlistend': 50,     # 限制前 50 个
            'quiet': True,
            'no_warnings': True,
            'proxy': os.environ.get("http_proxy") # 使用顶部定义的代理
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if 'entries' in info:
                    entries = list(info['entries']) # 生成列表
                    self.log_message(f"✅ 解析成功，共找到 {len(entries)} 个视频。")
                    # 在主线程打开选择窗口
                    self.after(0, lambda: self.open_selection_window(entries))
                else:
                    self.log_message("⚠️ 未找到视频或解析失败，尝试直接下载...")
                    self.current_download_urls = [url]
                    self.after(0, self.start_download_process)
                    
        except Exception as e:
            self.log_message(f"❌ 解析失败: {str(e)}")
            self.after(0, lambda: self.set_ui_state(processing=False))

    def open_selection_window(self, entries):
        """打开播放列表选择窗口"""
        
        # 创建 Toplevel 窗口
        selection_window = ctk.CTkToplevel(self)
        selection_window.title("选择要下载的视频")
        selection_window.geometry("500x600")
        selection_window.attributes("-topmost", True) # 置顶
        selection_window.grab_set() # 模态窗口
        
        # 1. 标题
        ctk.CTkLabel(selection_window, text=f"请选择视频 (共 {len(entries)} 个)", font=("Arial", 16, "bold")).pack(pady=10)
        
        # 2. 确认按钮 (关键：先 Pack 底部按钮，确保窗口缩小时按钮不被遮挡)
        checkboxes = [] # 预先定义

        def confirm():
            selected_urls = []
            for chk, var, url in checkboxes:
                if chk.get(): # Check if checked (1 or True)
                    selected_urls.append(url)

            if not selected_urls:
                messagebox.showwarning("提示", "请至少选择一个视频！")
                return
            
            selection_window.destroy()
            self.log_message(f"📝 用户已选择 {len(selected_urls)} 个视频，开始任务...")
            self.current_download_urls = selected_urls
            self.start_download_process()
            
        ctk.CTkButton(
            selection_window, 
            text="确认下载 (Confirm Download)", 
            command=confirm, 
            height=50
        ).pack(side="bottom", fill="x", padx=20, pady=10)

        # 3. 全选开关 (放在列表上方)
        def toggle_all():
            new_state = select_all_var.get()
            for chk, var, _ in checkboxes:
                var.set(new_state)
        
        select_all_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(selection_window, text="全选 (Select All)", variable=select_all_var, command=toggle_all).pack(pady=5)
        
        # 4. 滚动区域 (最后 Pack，占据剩余空间)
        scroll_frame = ctk.CTkScrollableFrame(selection_window, width=550) # Remove fixed height
        scroll_frame.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 5))
        
        # 填充内容
        for entry in entries:
            title = entry.get('title', 'Unknown Title')
            url = entry.get('url', entry.get('id')) 
            # 如果 url 只是 ID，补全它
            if url and not url.startswith('http'):
                url = f"https://www.youtube.com/watch?v={url}"
                
            var = ctk.BooleanVar(value=True) # 默认全选
            chk = ctk.CTkCheckBox(scroll_frame, text=title, variable=var, onvalue=True, offvalue=False)
            chk.pack(anchor="w", pady=2, padx=5)
            checkboxes.append((chk, var, url))

    def start_download_process(self):
        """启动下载流程 (设置 UI 并开启线程)"""
        self.stop_event.clear() # 重置暂停标志
        self.is_paused = False
        self.set_ui_state(downloading=True)
        
        # 开启下载线程
        threading.Thread(target=self.download_thread_logic, daemon=True).start()

    def set_ui_state(self, processing=False, downloading=False, paused=False):
        """统一管理 UI 状态"""
        # 恢复状态
        if not processing and not downloading:
            self.parse_btn.configure(state="normal", text="解析并下载")
            # 恢复大按钮显示
            self.pause_btn.pack_forget()
            self.resume_btn.pack_forget()
            self.parse_btn.pack(fill="x")
            self.url_entry.configure(state="normal")
            self.quality_combo.configure(state="normal")
            self.subtitle_menu.configure(state="normal")
            self.ipv6_switch.configure(state="normal")
            self.is_downloading = False
            return

        # 正在处理/下载
        # 正在处理/下载
        self.is_downloading = True
        
        # 隐藏大按钮
        self.parse_btn.pack_forget() 
        
        # 显示控制按钮 (在 Footer 中并排显示)
        self.pause_btn.pack(side="left", padx=5, fill="x", expand=True)
        self.resume_btn.pack(side="right", padx=5, fill="x", expand=True)
        
        self.url_entry.configure(state="disabled")
        self.quality_combo.configure(state="disabled")
        self.subtitle_menu.configure(state="disabled")
        self.ipv6_switch.configure(state="disabled")
        
        if paused:
            self.pause_btn.configure(state="disabled", fg_color="gray")
            self.resume_btn.configure(state="normal", fg_color="#27AE60")
        else:
            self.pause_btn.configure(state="normal", text="⏸️ 暂停下载", fg_color="#D35400")
            self.resume_btn.configure(state="disabled", fg_color="gray")

    def pause_download(self):
        """暂停动作"""
        if self.is_downloading and not self.is_paused:
            self.log_message("⏸️ 正在请求暂停... (将在当前分片完成后停止)")
            self.stop_event.set() # 设置停止标志
            self.is_paused = True
            self.set_ui_state(downloading=True, paused=True)

    def resume_download(self):
        """继续动作"""
        if self.is_paused:
            self.log_message("▶️ 正在恢复下载...")
            self.start_download_process() # 重新运行下载函数

    def progress_hook(self, d):
        """yt_dlp 进度钩子 (在此处检查暂停)"""
        if self.stop_event.is_set():
            raise PauseException("User paused the download")
            
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').replace('\x1b[0;94m', '').replace('\x1b[0m', '')
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            self.log_message(f"⬇️ 下载中... {percent} | 速度: {speed} | 剩余: {eta}")
        elif d['status'] == 'finished':
            self.log_message("📦 分片下载完成，准备处理...")

    def download_thread_logic(self):
        """核心下载逻辑 (在线程中运行)"""
        try:
            quality_choice = self.quality_combo.get()
            
            # 画质配置
            if quality_choice == "最高画质 (4K/8K)":
                format_str = "bestvideo+bestaudio/best"
            elif quality_choice == "1080p":
                format_str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best[height<=1080]"
            elif quality_choice == "720p":
                format_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=720]"
            else:
                format_str = "bestaudio/best"
                

                
            # current_dir = os.path.dirname(os.path.abspath(__file__)) # Obsolete
            save_path = get_app_path()
            
            # ffmpeg 检查
            ffmpeg_location = None
            current_dir = get_app_path() # Reuse get_app_path for ffmpeg check
            if os.path.exists(os.path.join(current_dir, "ffmpeg.exe")):
                ffmpeg_location = current_dir
            
            ydl_opts = {
                'format': format_str,
                'merge_output_format': 'mp4',
                'paths': {'home': save_path}, # Correct path for EXE
                'outtmpl': '%(title)s.%(ext)s', 
                'progress_hooks': [self.progress_hook], # 绑定钩子
                'no_warnings': True,
                
                # === NETWORK STABILITY FIXES (CRITICAL) ===
                'proxy': os.environ.get("http_proxy"),
                'retries': float('inf'),           # Infinite retries for HTTP errors
                'fragment_retries': float('inf'),  # Infinite retries for segment errors
                'skip_unavailable_fragments': False, # Never skip parts (keep trying)
                'socket_timeout': 30,              # Wait 30s before considering connection dead
                'force_ipv4': True,                # Default fix for 10054 (will be overridden if ipv6 checked)
                'ignoreerrors': True,              # Don't crash the whole app on one error
                'continuedl': True,                # Keep resume support
                # ==========================================
            }

            # IPv6 逻辑覆盖
            if self.ipv6_switch.get():
                ydl_opts['force_ipv4'] = False
                ydl_opts['force_ipv6'] = True
            else:
                ydl_opts['force_ipv4'] = True
                ydl_opts['force_ipv6'] = False
            
            
            if ffmpeg_location:
                ydl_opts['ffmpeg_location'] = ffmpeg_location
                
            # 字幕逻辑处理
            sub_choice = self.subtitle_menu.get()
            if sub_choice != '不下载 (None)':
                ydl_opts['writesubtitles'] = True
                if sub_choice == '中文 (Chinese)':
                    ydl_opts['subtitleslangs'] = ['zh-Hans', 'zh-CN', 'zh-TW', 'zh']
                elif sub_choice == '日语 (Japanese)':
                    ydl_opts['subtitleslangs'] = ['ja']
                elif sub_choice == '英语 (English)':
                    ydl_opts['subtitleslangs'] = ['en']
                elif sub_choice == '所有 (All)':
                    ydl_opts['subtitleslangs'] = ['all']
            else:
                ydl_opts['writesubtitles'] = False

            self.log_message(f"🚀 开始下载 {len(self.current_download_urls)} 个任务...")
            
            # === AUTO-RETRY LOGIC ===
            max_retries = 50  # Try up to 50 times (essentially infinite for user context)
            attempt = 0
            success = False
            
            while attempt < max_retries:
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download(self.current_download_urls)
                        success = True
                        break # If we get here, download finished successfully!
                
                except PauseException:
                    raise # Rethrow pause exception to be caught by outer block
                    
                except Exception as e:
                    attempt += 1
                    error_msg = str(e)
                    
                    # Update Log UI
                    self.log_message(f"⚠️ 网络不稳定，第 {attempt} 次重试中... (5秒后继续)")
                    print(f"Retry {attempt}/{max_retries}: {error_msg}")
                    
                    # Wait before retrying to let network recover
                    time.sleep(5)
                    
            if success:
                self.log_message("🎉 所有任务已全部完成！")
            else:
                self.log_message("❌ 重试次数过多，下载失败。请检查网络。")
            # ========================
            

            self.after(0, lambda: messagebox.showinfo("成功", "所有下载任务已完成！"))
            self.after(0, lambda: self.set_ui_state(downloading=False)) # 恢复初始状态

        except PauseException:
            # 捕获暂停异常
            self.log_message("🛑 下载已暂停。点击'继续下载'可恢复。")
            # 不需要恢复 UI 到 idle，因为它现在处于 paused 状态 (由 set_ui_state(paused=True) 处理)
            
        except Exception as e:
            self.log_message(f"❌ 发生错误: {str(e)}")
            self.after(0, lambda: messagebox.showerror("错误", f"下载出错: {str(e)}"))
            self.after(0, lambda: self.set_ui_state(downloading=False))
            
if __name__ == "__main__":
    app = YouTubeDownloader()
    app.mainloop()
