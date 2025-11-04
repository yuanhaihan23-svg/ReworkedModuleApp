import importlib
import sqlite3
import pymysql
import configparser
import sys, os
import tempfile

# ---------- 子表字段配置 ----------
SCHEMA_FIELDS = {
    "table_1_data": [
        ("timestamp", "TEXT"),
        ("quality_personnel", "TEXT"),
        ("protective_cover_installation_status", "TEXT"),
        ("foreign_matters_status", "TEXT"),
        ("protective_cover_appearance_status", "TEXT"),
        ("FPC_appearance_status", "TEXT"),
        ("FPC_foreign_matters_status", "TEXT"),
        ("end_plate_hole_appearance_status", "TEXT"),
        ("insulation_sheet_appearance_status", "TEXT"),
        ("side_plate_foam_appearance_status", "TEXT"),
        ("side_plate_appearance_status", "TEXT"),
        ("bottom_glue_clean_status", "TEXT"),
        ("module_bottom_picture", "TEXT"),
        ("tray_foam_status", "TEXT"),
        ("module_code_status", "TEXT"),
        ("module_hi_pot_test_status", "TEXT"),
    ],
    "table_2_data": [
        ("timestamp", "TEXT"),
        ("quality_personnel", "TEXT"),
        ("module_CMMtest_status", "TEXT"),
    ],
    "table_3_data": [
        ("timestamp", "TEXT"),
        ("quality_personnel", "TEXT"),
        ("voltage_status_consistent", "TEXT"),
        ("cell_batch_consistent", "TEXT"),
        ("module_grade_consistent", "TEXT"),
        ("module_unbound_status", "TEXT"),
    ],
}


# ---------- 路径工具 ----------
def resource_path(relative_path: str):
    """
    获取资源文件路径，兼容：
    ✅ 本地运行
    ✅ PyInstaller 打包环境（_MEIPASS）
    ✅ EXE 同目录
    """
    # 打包运行环境
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        # 如果是 exe 运行，则以 exe 所在目录为准
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.abspath(".")

    path = os.path.join(base_path, relative_path)

    # 最后兜底：若不存在 config.ini，则在 exe 同目录下创建
    if not os.path.exists(path) and relative_path.lower().endswith(".ini"):
        print(f"⚠️ 配置文件 {relative_path} 未找到，已自动生成默认配置。")
        config = configparser.ConfigParser()
        config["database"] = {"use_mysql": "False"}
        config["sqlite"] = {"path": "MyApp.db"}
        config["mysql"] = {
            "host": "localhost",
            "port": "3306",
            "user": "root",
            "password": "",
            "database": "mydb",
            "charset": "utf8mb4"
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                config.write(f)
            print(f"✅ 默认配置文件已生成：{path}")
        except Exception as e:
            print(f"⚠️ 创建配置文件失败：{e}")
    return path


class DB:

    def __init__(self):
        self.conn = None
        self.backend = None
        print("🚀 初始化数据库连接中...")
        self.config = self._load_config()

        # 检查 cryptography
        if self.config["use_mysql"] and not importlib.util.find_spec("cryptography"):
            print("⚠️ 缺少 cryptography 库，可能导致 MySQL 登录失败。请运行：pip install cryptography")

        # 根据配置连接数据库
        if self.config["use_mysql"]:
            self._connect_mysql()
        else:
            self._connect_sqlite()

        # 初始化表
        self._ensure_tables()

    # ---------- 加载配置 ----------
    def _load_config(self):
        config = configparser.ConfigParser()
        config_path = resource_path("config.ini")

        # 若存在则读取
        if os.path.exists(config_path):
            config.read(config_path, encoding="utf-8")

        # 否则使用默认值
        use_mysql = config.getboolean("database", "use_mysql", fallback=False)
        mysql_config = {
            "host": config.get("mysql", "host", fallback="localhost"),
            "port": config.getint("mysql", "port", fallback=3306),
            "user": config.get("mysql", "user", fallback="root"),
            "password": config.get("mysql", "password", fallback=""),
            "database": config.get("mysql", "database", fallback="mydb"),
            "charset": config.get("mysql", "charset", fallback="utf8mb4"),
        }
        sqlite_config = {"path": config.get("sqlite", "path", fallback="MyApp.db")}

        print(f"✅ 已加载配置文件：{config_path}")
        return {"use_mysql": use_mysql, "mysql": mysql_config, "sqlite": sqlite_config}

    # ---------- MySQL ----------
    def _connect_mysql(self):
        try:
            mysql_config = self.config["mysql"]
            self.conn = pymysql.connect(**mysql_config)
            self.backend = "mysql"
            print(f"✅ 已连接 MySQL 数据库：{mysql_config['host']}:{mysql_config['port']}")
        except Exception as e:
            print("⚠️ 无法连接 MySQL，自动切换到 SQLite：", e)
            self._connect_sqlite()

    # ---------- SQLite ----------
    def _connect_sqlite(self):
        sqlite_path = self.config["sqlite"]["path"]

        # ✅ 打包后，写入临时目录避免权限问题
        if getattr(sys, "_MEIPASS", None):
            tmp_dir = tempfile.gettempdir()
            sqlite_tmp_path = os.path.join(tmp_dir, os.path.basename(sqlite_path))
            if not os.path.exists(sqlite_tmp_path):
                open(sqlite_tmp_path, "a").close()
            sqlite_path = sqlite_tmp_path

        self.conn = sqlite3.connect(sqlite_path, check_same_thread=False)
        self.backend = "sqlite"
        print(f"✅ 已连接 SQLite 数据库：{sqlite_path}")

    # ---------- SQL 操作 ----------
    def _execute(self, sql, params=None):
        cur = self.conn.cursor()
        cur.execute(sql, params or ())
        return cur

    def _commit(self):
        try:
            self.conn.commit()
        except Exception as e:
            print("⚠️ 提交事务失败：", e)

    # ---------- 自动创建表 ----------
    def _ensure_tables(self):
        if self.backend == "mysql":
            create_master = """
            CREATE TABLE IF NOT EXISTS barcode_master (
                barcode VARCHAR(255) PRIMARY KEY,
                status_1 TINYINT DEFAULT 0,
                status_2 TINYINT DEFAULT 0,
                status_3 TINYINT DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        else:
            create_master = """
            CREATE TABLE IF NOT EXISTS barcode_master (
                barcode TEXT PRIMARY KEY,
                status_1 INTEGER DEFAULT 0,
                status_2 INTEGER DEFAULT 0,
                status_3 INTEGER DEFAULT 0
            );
            """
        self._execute(create_master)

        # 创建子表
        for tbl, fields in SCHEMA_FIELDS.items():
            if self.backend == "mysql":
                cols = ["id INT AUTO_INCREMENT PRIMARY KEY", "barcode VARCHAR(255)"]
                for n, t in fields:
                    cols.append(f"{n} {t}")
                sql = f"CREATE TABLE IF NOT EXISTS {tbl} ({', '.join(cols)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
            else:
                cols = ["id INTEGER PRIMARY KEY AUTOINCREMENT", "barcode TEXT"]
                for n, _ in fields:
                    cols.append(f"{n} TEXT")
                sql = f"CREATE TABLE IF NOT EXISTS {tbl} ({', '.join(cols)});"
            self._execute(sql)

            # 自动补列
            if self.backend == "sqlite":
                cur = self._execute(f"PRAGMA table_info({tbl});")
                existing = [r[1] for r in cur.fetchall()]
                for n, _ in fields:
                    if n not in existing:
                        print(f"🛠️ 添加缺失列 {n} 到 {tbl}")
                        self._execute(f"ALTER TABLE {tbl} ADD COLUMN {n} TEXT;")

        self._commit()
        print("🧱 数据表检查/创建完成")

    # ---------- 业务方法 ----------
    def ensure_barcode(self, barcode):
        sql = "INSERT OR IGNORE INTO barcode_master (barcode) VALUES (?);" if self.backend == "sqlite" \
            else "INSERT IGNORE INTO barcode_master (barcode) VALUES (%s);"
        self._execute(sql, (barcode,))
        self._commit()

    def get_status(self, barcode):
        sql = "SELECT status_1,status_2,status_3 FROM barcode_master WHERE barcode=?;" if self.backend == "sqlite" \
            else "SELECT status_1,status_2,status_3 FROM barcode_master WHERE barcode=%s;"
        cur = self._execute(sql, (barcode,))
        row = cur.fetchone()
        return tuple(int(x) for x in row) if row else (0, 0, 0)

    def update_status(self, barcode, s1=None, s2=None, s3=None):
        parts, vals = [], []
        if s1 is not None:
            parts.append("status_1=?") if self.backend == "sqlite" else parts.append("status_1=%s")
            vals.append(s1)
        if s2 is not None:
            parts.append("status_2=?") if self.backend == "sqlite" else parts.append("status_2=%s")
            vals.append(s2)
        if s3 is not None:
            parts.append("status_3=?") if self.backend == "sqlite" else parts.append("status_3=%s")
            vals.append(s3)
        if not parts:
            return
        vals.append(barcode)
        sql = f"UPDATE barcode_master SET {', '.join(parts)} WHERE barcode={'?' if self.backend == 'sqlite' else '%s'};"
        self._execute(sql, tuple(vals))
        self._commit()

    def insert_table(self, table, barcode, data):
        fields = list(data.keys())
        values = list(data.values())
        if self.backend == "sqlite":
            ph = ", ".join(["?"] * len(values))
            sql = f"INSERT INTO {table} (barcode, {', '.join(fields)}) VALUES (?, {ph});"
        else:
            ph = ", ".join(["%s"] * len(values))
            sql = f"INSERT INTO {table} (barcode, {', '.join(fields)}) VALUES (%s, {ph});"
        self._execute(sql, tuple([barcode] + values))
        self._commit()

    def fetch_table(self, table, barcode):
        fields = [n for n, _ in SCHEMA_FIELDS[table]]
        ph = "?" if self.backend == "sqlite" else "%s"
        sql = f"SELECT {', '.join(fields)} FROM {table} WHERE barcode={ph};"
        cur = self._execute(sql, (barcode,))
        row = cur.fetchone()
        return dict(zip(fields, row)) if row else {}

    def fetch_overview(self):
        cur = self._execute("SELECT barcode FROM barcode_master;")
        barcodes = [r[0] for r in cur.fetchall()]
        result = []
        for bc in barcodes:
            s1, s2, s3 = self.get_status(bc)
            total = self._calc_total_status(bc, s1, s2, s3)
            result.append((bc, s1, s2, s3, total))
        return result

    def _calc_total_status(self, barcode, s1, s2, s3):
        if not all([s1, s2, s3]):
            return "未完成"
        for tbl in SCHEMA_FIELDS:
            data = self.fetch_table(tbl, barcode)
            for v in data.values():
                if str(v).strip().upper() == "NG":
                    return "NG"
        return "OK"

    def fetch_quality_personnel_history(self):
        """从三个表中获取历史品质人员工号列表"""
        cursor = self.conn.cursor()
        history = set()
        for tbl in ["table_1_data", "table_2_data", "table_3_data"]:
            try:
                cursor.execute(
                    f"SELECT DISTINCT quality_personnel FROM {tbl} WHERE quality_personnel IS NOT NULL AND quality_personnel <> '';"
                )
                rows = cursor.fetchall()
                for r in rows:
                    history.add(str(r[0]).strip())
            except Exception as e:
                print(f"⚠️ 获取 {tbl} 历史记录失败: {e}")
                continue
        return sorted(history)
