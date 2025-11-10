import sys
import os
import tempfile
import atexit
from configparser import ConfigParser
from PyQt6.QtWidgets import QApplication, QMessageBox
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
        check_single_instance()

        # 初始化数据库
        db = DB()

        # 数据库未连接时弹窗提示并退出
        if not db.is_connected():
            QMessageBox.critical(
                None,
                "数据库连接失败",
                "❌ 无法连接到数据库，请检查网络或 config.ini 配置",
            )
            sys.exit(1)

        # 数据库连接成功，启动 GUI
        win = BarcodeApp(db=db)
        win.show()
        sys.exit(app.exec())

    except Exception as e:
        # 捕获其它异常并弹窗
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
