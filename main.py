import sys
import os
import tempfile
import atexit
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from gui import BarcodeApp  # 你的 GUI

# -------------------------------
# 防止重复启动
# -------------------------------
def check_single_instance():
    """
    防止重复启动：
    1. 写入 PID 文件
    2. 检查 PID 是否存在
    3. 如果 PID 不存在，则覆盖锁文件
    """
    lockfile = os.path.join(tempfile.gettempdir(), "MyApp.lock")

    if os.path.exists(lockfile):
        try:
            with open(lockfile, "r") as f:
                pid = int(f.read())
            if pid != os.getpid():
                if sys.platform == "win32":
                    try:
                        import psutil
                        if psutil.pid_exists(pid):
                            print("⚠️ 应用已在运行，禁止重复启动。")
                            sys.exit(0)
                    except ImportError:
                        print("⚠️ 应用可能已在运行（安装 psutil 可增强检测）。")
                        sys.exit(0)
                else:
                    try:
                        os.kill(pid, 0)
                        print("⚠️ 应用已在运行，禁止重复启动。")
                        sys.exit(0)
                    except OSError:
                        pass
        except Exception:
            pass

    # 写入当前 PID
    with open(lockfile, "w") as f:
        f.write(str(os.getpid()))

    # 程序退出时删除锁文件
    def remove_lock():
        try:
            if os.path.exists(lockfile):
                os.remove(lockfile)
        except Exception:
            pass

    atexit.register(remove_lock)

# -------------------------------
# 资源路径工具函数
# -------------------------------
def resource_path(relative_path: str):
    """让程序在 PyInstaller 打包后也能找到资源文件"""
    base_path = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return os.path.join(base_path, relative_path)


# -------------------------------
# ✅ 主程序入口
# -------------------------------
def main():
    # 启动 GUI
    app = QApplication(sys.argv)
    win = BarcodeApp()   # ✅ 传入数据库实例
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
