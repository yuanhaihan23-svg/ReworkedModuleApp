import os
import sys
import subprocess
import shutil
from pathlib import Path

# -------------------------------
# 资源路径函数
# -------------------------------
def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(Path(__file__).parent, relative_path)

# -------------------------------
# 清理旧构建
# -------------------------------
def clean_old_builds(project_dir: Path):
    for name in ["dist", "build", "main.spec"]:
        path = project_dir / name
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    print("🧹 已清理旧构建文件")

# -------------------------------
# 打包函数
# -------------------------------
def build_app():
    project_dir = Path(__file__).resolve().parent
    main_script = project_dir / "main.py"

    # 要打包的资源文件
    resources = ["config.ini", "db.py", "gui.py"]
    add_data_args = [f"--add-data={project_dir / f}:{'.'}" for f in resources]

    # 图标
    icon_file = project_dir / "icon.icns"
    icon_param = [f"--icon={icon_file}"] if icon_file.exists() else []

    # 清理旧构建
    clean_old_builds(project_dir)

    # -------------------------------
    # ✅ 打包命令（onedir 模式，启动更快）
    # -------------------------------
    cmd = [
        "pyinstaller",
        "--onedir",        # 👈 改为 onedir，避免每次解压
        "--windowed",
        "--noconfirm",
        "--name", "MyApp",
        *add_data_args,
        *icon_param,
        str(main_script)
    ]

    print("\n🚀 正在执行打包命令：")
    print(" ".join(str(x) for x in cmd))

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 打包失败: {e}")
        sys.exit(1)

    dist_app = project_dir / "dist" / "MyApp.app"

    # -------------------------------
    # macOS: 移除隔离属性 + 权限修复
    # -------------------------------
    if dist_app.exists():
        subprocess.run(["xattr", "-rd", "com.apple.quarantine", str(dist_app)], check=False)
        subprocess.run(["chmod", "-R", "+x", str(dist_app)], check=False)

    subprocess.run(["open", str(project_dir / "dist")], check=False)
    print("✅ 打包完成！可在 dist/MyApp.app 启动")

# -------------------------------
# 主入口
# -------------------------------
if __name__ == "__main__":
    build_app()
