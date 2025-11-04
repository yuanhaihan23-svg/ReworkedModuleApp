import sys
import os
import tempfile
import atexit
from pathlib import Path
from configparser import ConfigParser
from PyQt6.QtWidgets import QApplication
from gui import BarcodeApp  # 你的 GUI
from db import DB

# -------------------------------
# 防止重复启动
# -------------------------------
def check_single_instance():
    lockfile = os.path.join(tempfile.gettempdir(), "MyApp.lock")
    if os.path.exists(lockfile):
        try:
            with open(lockfile, "r") as f:
                pid = int(f.read())
            if pid != os.getpid():
                try:
                    os.kill(pid, 0)
                    print("⚠️ 应用已在运行，禁止重复启动。")
                    sys.exit(0)
                except OSError:
                    pass
        except Exception:
            pass

    with open(lockfile, "w") as f:
        f.write(str(os.getpid()))

    def remove_lock():
        if os.path.exists(lockfile):
            os.remove(lockfile)

    atexit.register(remove_lock)

# -------------------------------
# 资源路径工具函数
# -------------------------------
def resource_path(relative_path: str):
    """让程序在 PyInstaller 打包后也能找到资源文件"""
    base_path = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return os.path.join(base_path, relative_path)

# -------------------------------
# 读取数据库配置
# -------------------------------
def load_config():
    config_file = resource_path("config.ini")
    config = ConfigParser()
    config.read(config_file, encoding="utf-8")
    return config

# -------------------------------
# 主程序入口
# -------------------------------


def main():
    db = DB()  # 自动读取 app 文件夹下 config.ini
    app = QApplication(sys.argv)
    win = BarcodeApp(db=db)  # GUI 内使用 db 实例
    win.show()
    sys.exit(app.exec())
if __name__ == "__main__":
    main()
