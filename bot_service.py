import os
import json
import logging
import asyncio
import urllib.request
import urllib.error
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from openai import OpenAI
from PIL import ImageGrab

logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}

def check_health(token: str, api_key: str) -> str:
    """
    Returns one of: "正常", "tg机器人连接失败", "aiapi连接失败", "网络错误", "未知问题"
    """
    if not token or not api_key:
        return "未知问题"

    # 1. Test Telegram
    tg_url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        req = urllib.request.Request(tg_url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                return "tg机器人连接失败"
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError) or "getaddrinfo failed" in str(e.reason):
            return "网络错误"
        return "tg机器人连接失败"
    except Exception:
        return "tg机器人连接失败"

    # 2. Test DeepSeek API
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1", max_retries=1)
        # Using a very lightweight models list call
        client.models.list(timeout=10)
    except Exception as e:
        err_str = str(e).lower()
        if "timeout" in err_str or "connection" in err_str:
            return "网络错误"
        return "aiapi连接失败"

    return "正常"

SYSTEM_PROMPT = """You are a natural language command interpreter for a Windows computer.
Your ONLY job is to classify the user's intent into exactly ONE of the following keywords.
Do not provide any conversational text, explanations, or markdown formatting. ONLY output the exact keyword and nothing else.

Keywords:
- SHUTDOWN (for shutting down the PC)
- RESTART (for restarting the PC)
- SLEEP (for putting the PC to sleep)
- CLOSE_ALL_WINDOWS (for safely closing all open application windows)
- MINIMIZE_ALL_WINDOWS (for minimizing all windows to show desktop)
- MUTE (for muting or toggling the computer's volume)
- LOCK_SCREEN (for locking the Windows screen)
- UNLOCK (for authorizing to unlock the Windows lock screen)
- SCREENSHOT (for capturing the current screen/taking a screenshot)
- HELP (for asking what the bot can do, available commands, features, etc.)
- VOLUME_UP (for increasing the system volume slightly)
- VOLUME_DOWN (for decreasing the system volume slightly)
- VOLUME_MAX (for setting the volume to 100%)
- VOLUME_SET:X (for setting the volume to a specific percentage X, where X is 0-100. Example: VOLUME_SET:30)
- UNKNOWN (if the intent is unclear or not one of the above)"""

class BotService:
    def __init__(self):
        self.app = None
        self.running = False

    def get_intent(self, user_input: str, api_key: str, base_url: str, model: str) -> str:
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.0
            )
            content = response.choices[0].message.content.strip().upper()
            
            # Remove any markdown code block formatting that some models add
            content = content.replace("```", "").replace("TEXT", "").replace("MARKDOWN", "").strip()
            
            import re
            match = re.search(r"VOLUME_SET:\s*(\d+)", content)
            if match:
                return f"VOLUME_SET:{match.group(1)}"
                
            keywords = [
                "SHUTDOWN", "RESTART", "SLEEP", "CLOSE_ALL_WINDOWS", 
                "MINIMIZE_ALL_WINDOWS", "MUTE", "LOCK_SCREEN", "UNLOCK",
                "SCREENSHOT", "HELP", "VOLUME_UP", "VOLUME_DOWN", "VOLUME_MAX"
            ]
            
            # First try exact match
            for kw in keywords:
                if content == kw:
                    return kw
                    
            # Fallback to substring match for chatty models
            for kw in keywords:
                if kw in content:
                    return kw
                    
            return "UNKNOWN"
        except Exception as e:
            logger.error(f"Error calling AI API: {e}")
            return "UNKNOWN"

    def set_system_volume(self, volume_level: int):
        volume_level = max(0, min(100, volume_level))
        ps_script = f"""
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {{
    int f(); int g(); int h(); int i();
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
    int j(); int k(); int l(); int m(); int n(); int o(); int p();
}}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice {{
    int Activate(ref System.Guid id, int clsCtx, int activationParams, out IAudioEndpointVolume aev);
}}
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator {{
    int f();
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint);
}}
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumeratorComObject {{ }}
public class Audio {{
    public static void SetVolume(int volume) {{
        IMMDeviceEnumerator deviceEnumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
        IMMDevice device;
        deviceEnumerator.GetDefaultAudioEndpoint(0, 1, out device);
        System.Guid aevGuid = typeof(IAudioEndpointVolume).GUID;
        IAudioEndpointVolume aev;
        device.Activate(ref aevGuid, 1, 0, out aev);
        aev.SetMasterVolumeLevelScalar(volume / 100f, System.Guid.Empty);
    }}
}}
'@
[Audio]::SetVolume({volume_level})
"""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as f:
            f.write(ps_script)
            temp_path = f.name
        os.system(f'powershell -ExecutionPolicy Bypass -File "{temp_path}"')
        os.remove(temp_path)

    def execute_command(self, intent: str, config: dict) -> dict:
        if intent == "SHUTDOWN":
            os.system("shutdown /s /t 0")
            return {"type": "text", "content": "关机命令已执行，预计需要1分钟，关机后远程控制将不可用"}
        elif intent == "RESTART":
            os.system("shutdown /r /t 0")
            return {"type": "text", "content": "重启命令已执行，预计需要1分钟，重启期间远程控制将短暂不可用"}
        elif intent == "SLEEP":
            os.system('powershell -Command "Add-Type -Assembly System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState(\'Suspend\', $false, $false)"')
            return {"type": "text", "content": "睡眠命令已执行，设备即将进入休眠状态，网络连接将断开"}
        elif intent == "CLOSE_ALL_WINDOWS":
            os.system('powershell -Command "Get-Process | Where-Object {$_.MainWindowHandle -ne 0 -and $_.ProcessName -ne \'explorer\'} | ForEach-Object { $_.CloseMainWindow() }"')
            return {"type": "text", "content": "关闭窗口命令已执行，已向所有正在运行的应用程序发送安全退出请求"}
        elif intent == "MINIMIZE_ALL_WINDOWS":
            os.system('powershell -Command "(New-Object -ComObject Shell.Application).MinimizeAll()"')
            return {"type": "text", "content": "最小化命令已执行，所有窗口均已隐藏并显示桌面"}
        elif intent == "MUTE":
            os.system('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"')
            return {"type": "text", "content": "静音切换命令已执行，系统主音量状态已更改"}
        elif intent == "LOCK_SCREEN":
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return {"type": "text", "content": "锁屏命令已执行，系统屏幕已锁定，需要重新输入密码解锁"}
        elif intent == "SCREENSHOT":
            img_path = os.path.join(os.path.dirname(__file__), "screenshot.png")
            screenshot = ImageGrab.grab()
            screenshot.save(img_path)
            return {"type": "photo", "path": img_path}
        elif intent == "UNLOCK":
            username = config.get("windows_username", "")
            password = config.get("windows_password", "")
            
            if not username or not password:
                return {"type": "text", "content": "解锁失败：未在面板中配置 Windows 凭据。"}
                
            try:
                import win32file
                pipe = win32file.CreateFile(
                    r'\\.\pipe\TGUnlockPipe',
                    win32file.GENERIC_WRITE,
                    0, None,
                    win32file.OPEN_EXISTING,
                    0, None
                )
                password_str = f"UNLOCK:{password}".encode('utf-8')
                win32file.WriteFile(pipe, password_str)
                win32file.CloseHandle(pipe)
                logger.info("Sent password to TGUnlockPipe")
                return {"type": "text", "content": "✅ 已单次授权登录\n本次解锁已成功！出于安全考虑，下次锁屏系统仍会自动锁定，需再次授权或手动输入密码。"}
            except Exception as e:
                logger.error(f"Unlock failed: {e}")
                return {"type": "text", "content": f"解锁失败：提供程序可能未运行（确保已在锁屏界面），详细信息：{e}"}
        elif intent == "HELP":
            help_text = (
                "可用功能及命令（支持自然语言，直接发送意思相近的话即可）：\n"
                "- 🔓 锁屏解锁：发送“解锁屏幕”、“帮我解锁”等\n"
                "- 📸 屏幕截图：发送“截图”、“看看屏幕”等\n"
                "- 🔒 锁定屏幕：发送“锁屏”\n"
                "- 🔌 电源管理：发送“关机”、“重启”、“睡眠”等\n"
                "- 🧹 窗口管理：发送“关闭所有窗口”、“最小化所有窗口”等\n"
                "- 🔊 音量控制：发送“大声点”、“音量调到30%”、“静音”、“最大声”等"
            )
            return {"type": "text", "content": help_text}
        elif intent == "VOLUME_UP":
            import ctypes
            for _ in range(5): # Increase by 10% (5 steps of 2%)
                ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
            return {"type": "text", "content": "🔊 音量已调大"}
        elif intent == "VOLUME_DOWN":
            import ctypes
            for _ in range(5): # Decrease by 10%
                ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
            return {"type": "text", "content": "🔉 音量已调小"}
        elif intent == "VOLUME_MAX":
            self.set_system_volume(100)
            return {"type": "text", "content": "🔊 音量已调至最大 (100%)"}
        elif intent.startswith("VOLUME_SET:"):
            try:
                vol = int(intent.split(":")[1])
                self.set_system_volume(vol)
                return {"type": "text", "content": f"🔉 音量已准确设置为 {vol}%"}
            except Exception as e:
                logger.error(f"Set volume failed: {e}")
                return {"type": "text", "content": "设置音量失败"}
        else:
            return {"type": "text", "content": "未识别到有效指令，请发送明确的控制指令"}

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        config = load_config()
        
        # Check if enabled
        if not config.get("is_enabled", True):
            return

        user_id = update.effective_user.id
        allowed_id = config.get("telegram_user_id", "")
        
        # Security Authorization check: strictly compare the user ID
        try:
            if str(user_id) != str(allowed_id):
                logger.warning(f"SECURITY ALERT: Unauthorized access attempt from user ID: {user_id}. Message ignored.")
                # We purposefully do not reply to unauthorized users to avoid exposing the bot's existence
                return
        except ValueError:
            pass

        text = update.message.text
        if not text:
            return
            
        logger.info(f"Received command: {text}")
        api_key = config.get("ai_api_key", config.get("deepseek_api_key", ""))
        base_url = config.get("ai_base_url", "https://api.deepseek.com/v1")
        model = config.get("ai_model", "deepseek-chat")
        
        if not api_key:
            await update.message.reply_text("未配置 AI 大模型 API Key。")
            return

        intent = self.get_intent(text, api_key, base_url, model)
        logger.info(f"Classified Intent: {intent}")
        
        response = self.execute_command(intent, config)
        
        if response["type"] == "text":
            await update.message.reply_text(response["content"])
        elif response["type"] == "photo":
            try:
                with open(response["path"], "rb") as photo:
                    await update.message.reply_photo(photo=photo, caption="屏幕截图获取成功，这是当前的系统画面")
                # Clean up the file after sending
                if os.path.exists(response["path"]):
                    os.remove(response["path"])
            except Exception as e:
                logger.error(f"Failed to send screenshot: {e}")
                await update.message.reply_text("获取屏幕截图失败。")

    def start(self):
        config = load_config()
        token = config.get("telegram_bot_token", "")
        if not token:
            logger.error("No token provided, bot not starting.")
            return

        # Initialize the Telegram Bot
        self.app = Application.builder().token(token).build()
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info("Starting Telegram polling...")
        
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        self.running = True
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
        self.running = False

    def stop(self):
        if self.app and self.app.updater:
            logger.info("Stopping bot...")
            asyncio.run(self.app.updater.stop())
            asyncio.run(self.app.stop())
            asyncio.run(self.app.shutdown())
        self.running = False
