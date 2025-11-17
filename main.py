import sys
import os
import tempfile
import atexit
from PyQt6.QtWidgets import QApplication, QMessageBox
import configparser

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
                    print("⚠️ The application is already running. Do not restart it")
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
    if getattr(sys, "frozen", False):  # PyInstaller 打包
        base_path = sys._MEIPASS
    else:  # 本地运行
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


# -------------------------------
# 读取数据库配置
# -------------------------------
def load_config():
    config = configparser.ConfigParser()
    config_file = resource_path("config.ini")
    config.read(config_file, encoding="utf-8")
    return config

# -------------------------------
# 读取品质人员白名单
# -------------------------------
def load_whitelist():
    """
    从 config.ini 的 [auth] 节读取 whitelist。
    返回一个 set，所有元素都是字符串。
    """
    config = load_config()
    wl_str = config.get("auth", "whitelist", fallback=None)

    if wl_str is None:
        return set()

    whitelist = {item.strip() for item in wl_str.split(",") if item.strip()}
    return whitelist




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
                "Database connection failed",
                "❌ Unable to connect to the database. Please check your network or config.ini configuration",
            )
            sys.exit(1)
        whitelist = load_whitelist()
        # 数据库连接成功，启动 GUI
        win = BarcodeApp(db=db, whitelist=whitelist)
        win.show()
        sys.exit(app.exec())

    except Exception as e:
        # 捕获其它异常并弹窗
        import traceback

        msg = QMessageBox()
        msg.setWindowTitle("Program exception")
        msg.setText("An error occurred in the program:\n" + str(e))
        msg.setDetailedText(traceback.format_exc())
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.exec()
        sys.exit(1)

if __name__ == "__main__":
    main()

