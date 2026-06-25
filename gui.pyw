import os
import json
import threading
import time
import datetime
import ctypes
import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw
import sys

from bot_service import BotService, load_config, CONFIG_FILE, check_health
from setup_shortcuts import toggle_autostart, is_autostart_enabled

# Initialize Bot Service
bot_service = BotService()

START_TIME = time.time()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Telegram PC Control")
        self.geometry("400x600")
        
        # Apply simple transparency to avoid DWM rendering bugs
        self.attributes("-alpha", 0.90)
        
        # Load configs
        self.config = load_config()
        
        # Frames for sliding animation
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.auth_frame = ctk.CTkFrame(self, fg_color="transparent")
        
        self.main_frame.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=1.0)
        self.settings_frame.place(relx=1.0, rely=0.0, relwidth=1.0, relheight=1.0)
        self.auth_frame.place(relx=-1.0, rely=0.0, relwidth=1.0, relheight=1.0)
        
        self.build_main_frame()
        self.build_settings_frame()
        self.build_auth_frame()
        
        # Protocol for closing window (minimize to tray)
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Start bot thread
        self.bot_thread = threading.Thread(target=bot_service.start, daemon=True)
        self.bot_thread.start()
        
        # Start timers
        self.update_uptime()
        
        # Start initial health check
        self.run_health_check()

    def build_main_frame(self):
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(self.main_frame, text="Telegram PC 控制端", font=("Arial", 22, "bold"))
        title_label.grid(row=0, column=0, pady=(40, 20))
        
        # Status Label
        self.status_label = ctk.CTkLabel(self.main_frame, text="自检状态: 等待检测...", font=("Arial", 16), text_color="#FFA500")
        self.status_label.grid(row=1, column=0, pady=(10, 10))
        
        # Uptime Label
        self.uptime_label = ctk.CTkLabel(self.main_frame, text="已运行: 00:00:00", font=("Arial", 16))
        self.uptime_label.grid(row=2, column=0, pady=(0, 30))
        
        # Buttons
        self.is_enabled = ctk.BooleanVar(value=self.config.get("is_enabled", True))
        self.switch = ctk.CTkSwitch(self.main_frame, text="开启机器人功能", variable=self.is_enabled, command=self.save_config)
        self.switch.grid(row=3, column=0, pady=10)
        
        self.is_autostart = ctk.BooleanVar(value=is_autostart_enabled())
        self.autostart_switch = ctk.CTkSwitch(self.main_frame, text="开启最高权限开机自启", variable=self.is_autostart, command=self.toggle_autostart_setting)
        self.autostart_switch.grid(row=4, column=0, pady=10)
        
        api_btn = ctk.CTkButton(self.main_frame, text="API 接口设置", command=self.slide_to_settings)
        api_btn.grid(row=5, column=0, pady=(20, 10))
        
        auth_btn = ctk.CTkButton(self.main_frame, text="锁屏解锁设置", fg_color="#FBC02D", hover_color="#F57F17", text_color="#000", command=self.slide_to_auth)
        auth_btn.grid(row=6, column=0, pady=10)
        
        quit_btn = ctk.CTkButton(self.main_frame, text="彻底关闭程序", fg_color="#D32F2F", hover_color="#B71C1C", command=self.quit_app)
        quit_btn.grid(row=7, column=0, pady=10)

    def build_settings_frame(self):
        self.settings_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(self.settings_frame, text="API 接口设置", font=("Arial", 22, "bold"))
        title_label.grid(row=0, column=0, pady=(40, 20))
        
        self.ds_label = ctk.CTkLabel(self.settings_frame, text="DeepSeek API Key:")
        self.ds_label.grid(row=1, column=0, sticky="w", padx=20)
        self.ds_entry = ctk.CTkEntry(self.settings_frame, width=360, show="*")
        self.ds_entry.grid(row=2, column=0, padx=20, pady=5)
        self.ds_entry.insert(0, self.config.get("deepseek_api_key", ""))
        
        self.tg_label = ctk.CTkLabel(self.settings_frame, text="Telegram Bot Token:")
        self.tg_label.grid(row=3, column=0, sticky="w", padx=20, pady=(10, 0))
        self.tg_entry = ctk.CTkEntry(self.settings_frame, width=360, show="*")
        self.tg_entry.grid(row=4, column=0, padx=20, pady=5)
        self.tg_entry.insert(0, self.config.get("telegram_bot_token", ""))
        
        self.uid_label = ctk.CTkLabel(self.settings_frame, text="Your Telegram User ID:")
        self.uid_label.grid(row=5, column=0, sticky="w", padx=20, pady=(10, 0))
        self.uid_entry = ctk.CTkEntry(self.settings_frame, width=360)
        self.uid_entry.grid(row=6, column=0, padx=20, pady=5)
        self.uid_entry.insert(0, self.config.get("telegram_user_id", ""))
        
        save_btn = ctk.CTkButton(self.settings_frame, text="保存设置", command=self.save_config)
        save_btn.grid(row=7, column=0, pady=(30, 10))
        
        back_btn = ctk.CTkButton(self.settings_frame, text="返回主菜单", fg_color="gray", hover_color="darkgray", command=self.slide_to_main_from_settings)
        back_btn.grid(row=8, column=0, pady=10)

    def build_auth_frame(self):
        self.auth_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(self.auth_frame, text="锁屏解锁设置", font=("Arial", 22, "bold"), text_color="#FBC02D")
        title_label.grid(row=0, column=0, pady=(40, 20))
        
        desc_label = ctk.CTkLabel(self.auth_frame, text="提供凭据以授权机器人强行穿透锁屏界面。\n密码仅保存在本地。", text_color="#AAAAAA")
        desc_label.grid(row=1, column=0, pady=(0, 20))
        
        self.win_usr_label = ctk.CTkLabel(self.auth_frame, text="Windows 登录用户名:")
        self.win_usr_label.grid(row=2, column=0, sticky="w", padx=20)
        self.win_usr_entry = ctk.CTkEntry(self.auth_frame, width=360)
        self.win_usr_entry.grid(row=3, column=0, padx=20, pady=5)
        self.win_usr_entry.insert(0, self.config.get("windows_username", os.getlogin()))
        
        self.win_pwd_label = ctk.CTkLabel(self.auth_frame, text="Windows 登录密码:")
        self.win_pwd_label.grid(row=4, column=0, sticky="w", padx=20, pady=(10, 0))
        self.win_pwd_entry = ctk.CTkEntry(self.auth_frame, width=360, show="*")
        self.win_pwd_entry.grid(row=5, column=0, padx=20, pady=5)
        self.win_pwd_entry.insert(0, self.config.get("windows_password", ""))
        
        save_btn = ctk.CTkButton(self.auth_frame, text="保存凭据", command=self.save_config)
        save_btn.grid(row=6, column=0, pady=(30, 10))
        
        install_btn = ctk.CTkButton(self.auth_frame, text="一键安装/更新解锁驱动", fg_color="#1E88E5", hover_color="#1565C0", command=self.install_dll)
        install_btn.grid(row=7, column=0, pady=10)
        
        back_btn = ctk.CTkButton(self.auth_frame, text="返回主菜单", fg_color="gray", hover_color="darkgray", command=self.slide_to_main_from_auth)
        back_btn.grid(row=8, column=0, pady=10)

    def install_dll(self):
        install_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TGUnlockProvider", "install.bat")
        if os.path.exists(install_script):
            ctypes.windll.shell32.ShellExecuteW(None, "runas", install_script, "", "", 1)

    def toggle_autostart_setting(self):
        toggle_autostart(self.is_autostart.get())

    def update_uptime(self):
        uptime_seconds = int(time.time() - START_TIME)
        uptime_str = str(datetime.timedelta(seconds=uptime_seconds))
        self.uptime_label.configure(text=f"已运行: {uptime_str}")
        self.after(1000, self.update_uptime)

    def run_health_check(self):
        self.status_label.configure(text="自检状态: 检测中...", text_color="#FFA500")
        
        def check_task():
            status = check_health(self.config.get("telegram_bot_token", ""), self.config.get("deepseek_api_key", ""))
            self.after(0, lambda: self.update_health_status(status))
            self.after(3600000, self.run_health_check)
            
        threading.Thread(target=check_task, daemon=True).start()

    def update_health_status(self, status):
        color = "#00FF00" if status == "正常" else "#FF0000"
        self.status_label.configure(text=f"自检状态: {status}", text_color=color)

    # --- Animation Logic ---
    def slide_to_settings(self):
        self.animate_slide(self.main_frame, self.settings_frame, 0.0, 1.0, -1.0, 0.0)

    def slide_to_main_from_settings(self):
        self.animate_slide(self.settings_frame, self.main_frame, 0.0, -1.0, 1.0, 0.0)

    def slide_to_auth(self):
        self.animate_slide(self.main_frame, self.auth_frame, 0.0, -1.0, 1.0, 0.0)

    def slide_to_main_from_auth(self):
        self.animate_slide(self.auth_frame, self.main_frame, 0.0, 1.0, -1.0, 0.0)

    def animate_slide(self, frame_out, frame_in, start_out, start_in, target_out, target_in):
        steps = 20
        duration = 0.2  
        delay = int((duration / steps) * 1000)
        
        step_out = (target_out - start_out) / steps
        step_in = (target_in - start_in) / steps
        
        def do_step(current_step):
            relx_out = start_out + (step_out * current_step)
            relx_in = start_in + (step_in * current_step)
            
            frame_out.place(relx=relx_out, rely=0.0, relwidth=1.0, relheight=1.0)
            frame_in.place(relx=relx_in, rely=0.0, relwidth=1.0, relheight=1.0)
            
            if current_step < steps:
                self.after(delay, lambda: do_step(current_step + 1))
            else:
                frame_out.place(relx=target_out, rely=0.0, relwidth=1.0, relheight=1.0)
                frame_in.place(relx=target_in, rely=0.0, relwidth=1.0, relheight=1.0)
                
        do_step(1)

    def save_config(self):
        new_config = {
            "deepseek_api_key": self.ds_entry.get().strip(),
            "telegram_bot_token": self.tg_entry.get().strip(),
            "telegram_user_id": self.uid_entry.get().strip(),
            "windows_username": self.win_usr_entry.get().strip(),
            "windows_password": self.win_pwd_entry.get().strip(),
            "is_enabled": self.is_enabled.get()
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=4)
        self.config = new_config
        self.run_health_check()

    def hide_window(self):
        self.withdraw()
        image = Image.new('RGB', (64, 64), color=(0, 128, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((16, 16, 48, 48), fill=(255, 255, 255))

        menu = pystray.Menu(
            pystray.MenuItem('显示界面', self.show_window),
            pystray.MenuItem('退出', self.quit_app)
        )
        self.tray_icon = pystray.Icon("name", image, "Telegram PC Control", menu)
        
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon=None, item=None):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.after(0, self.deiconify)

    def quit_app(self, icon=None, item=None):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        bot_service.stop()
        self.quit()
        sys.exit(0)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if __name__ == "__main__":
    if not is_admin():
        # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', None, 1)
        sys.exit()

    ctk.set_appearance_mode("dark")
    app = App()
    app.mainloop()
