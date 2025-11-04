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
def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
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
    try:
        app = QApplication(sys.argv)  # 先创建 QApplication
        db = DB()  # 再初始化数据库

        win = BarcodeApp(db=db)
        win.show()

        sys.exit(app.exec())
    except Exception as e:
        # 在 EXE 环境下用 QMessageBox 弹出异常
        from PyQt6.QtWidgets import QMessageBox
        import traceback

        msg = QMessageBox()
        msg.setWindowTitle("程序异常")
        msg.setText("程序发生错误:\n" + str(e))
        msg.setDetailedText(traceback.format_exc())
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.exec()
        sys.exit(1)


if __name__ == "__main__":
    main()
