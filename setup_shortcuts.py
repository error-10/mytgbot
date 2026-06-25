import os
import sys
import ctypes
import subprocess

TASK_NAME = "TelegramPCControlAutoStart"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_script_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "gui.pyw")

def get_pythonw_path():
    return sys.executable.replace("python.exe", "pythonw.exe")

def is_autostart_enabled():
    try:
        # Check if scheduled task exists
        result = subprocess.run(["schtasks", "/query", "/tn", TASK_NAME], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return result.returncode == 0
    except Exception:
        return False

def toggle_autostart(enable: bool):
    script_path = get_script_path()
    pythonw_path = get_pythonw_path()
    
    if enable:
        if not is_admin():
            print("Requires administrator privileges to create a scheduled task.")
            # Request elevation
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{os.path.abspath(__file__)}" enable', None, 1)
            return

        command = f'"{pythonw_path}" "{script_path}"'
        # Create a scheduled task to run on user logon with highest privileges
        try:
            # First try to delete it if it exists to avoid errors
            subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Create task
            cmd = [
                "schtasks", "/create",
                "/tn", TASK_NAME,
                "/tr", command,
                "/sc", "ONLOGON",
                "/rl", "HIGHEST",
                "/f"
            ]
            subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            print("Autostart task created successfully.")
        except Exception as e:
            print(f"Failed to create scheduled task: {e}")
    else:
        if not is_admin():
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{os.path.abspath(__file__)}" disable', None, 1)
            return
            
        try:
            subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            print("Autostart task removed successfully.")
        except Exception as e:
            print(f"Failed to remove scheduled task: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "enable":
            toggle_autostart(True)
        elif sys.argv[1] == "disable":
            toggle_autostart(False)
