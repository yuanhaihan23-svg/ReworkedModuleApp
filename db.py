import importlib
import pymysql
import configparser
import sys, os


# ---------- 表字段配置 ----------
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
        ("module_code_status", "TEXT")
    ],
    "table_2_data": [
        ("timestamp", "TEXT"),
        ("quality_personnel", "TEXT"),
        ("module_CMMtest_status", "TEXT"),
    ],
    "table_3_data": [
        ("timestamp", "TEXT"),
        ("quality_personnel", "TEXT"),
        ("sampling_data_status","TEXT"),
        ("voltage_status_consistent", "TEXT"),
        ("cell_batch_consistent", "TEXT"),
        ("module_grade_consistent", "TEXT"),
        ("module_unbound_status", "TEXT"),
        ("module_appearance_status", "TEXT")
    ],
}


# ---------- 路径工具 ----------
def resource_path(relative_path: str):
    """兼容 PyInstaller 打包与本地运行的路径"""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    elif getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")

    path = os.path.join(base_path, relative_path)

    # 自动生成默认配置文件
    if not os.path.exists(path) and relative_path.lower().endswith(".ini"):
        print(f"⚠️ 未找到配置文件 {relative_path}，已自动创建默认 config.ini")
        config = configparser.ConfigParser()
        config["database"] = {"use_mysql": "True"}
        config["mysql"] = {
            "host": "10.100.4.160",
            "port": "3306",
            "user": "remoteuser",
            "password": "password123456",
            "database": "rework module status",
            "charset": "utf8mb4"
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                config.write(f)
        except Exception as e:
            print(f"⚠️ 写入配置文件失败: {e}")
    return path


# ---------- 主类 ----------
class DB:
    """仅使用 MySQL，不回退至 SQLite"""

    def __init__(self):
        print("🚀 初始化远程数据库连接中...")
        self.conn = None
        self.connected = False
        self.config = self._load_config()
        self._connect_mysql()

        # 若连接成功则确保表结构存在
        if self.connected:
            self._ensure_tables()

    # ---------- 加载配置 ----------
    def _load_config(self):
        config = configparser.ConfigParser()
        config_path = resource_path("config.ini")

        if os.path.exists(config_path):
            config.read(config_path, encoding="utf-8")

        mysql_cfg = {
            "host": config.get("mysql", "host", fallback="localhost"),
            "port": config.getint("mysql", "port", fallback=3306),
            "user": config.get("mysql", "user", fallback="root"),
            "password": config.get("mysql", "password", fallback=""),
            "database": config.get("mysql", "database", fallback="test"),
            "charset": config.get("mysql", "charset", fallback="utf8mb4"),
        }
        print(f"✅ 已加载配置文件: {config_path}")
        return mysql_cfg

    # ---------- MySQL ----------
    def _connect_mysql(self):
        try:
            if not importlib.util.find_spec("pymysql"):
                raise ImportError("缺少 pymysql 模块，请先安装：pip install pymysql")

            self.conn = pymysql.connect(**self.config)
            self.connected = True
            print(f"✅ 成功连接 MySQL 数据库：{self.config['host']}:{self.config['port']}")
        except Exception as e:
            self.connected = False
            print("❌ 无法连接 MySQL 数据库：", e)

    def is_connected(self):
        """返回连接状态"""
        return self.connected

    # ---------- SQL 执行 ----------
    def _execute(self, sql, params=None):
        if not self.connected:
            print("⚠️ 数据库未连接，无法执行 SQL。")
            return None
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params or ())
            return cur
        except Exception as e:
            print(f"⚠️ SQL 执行失败：{e}\nSQL: {sql}")
            return None

    def _commit(self):
        if self.connected:
            try:
                self.conn.commit()
            except Exception as e:
                print("⚠️ 提交失败：", e)

    # ---------- 表初始化 ----------
    def _ensure_tables(self):
        create_master = """
        CREATE TABLE IF NOT EXISTS barcode_master (
            barcode VARCHAR(255) PRIMARY KEY,
            status_1 TINYINT DEFAULT 0,
            status_2 TINYINT DEFAULT 0,
            status_3 TINYINT DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self._execute(create_master)

        for tbl, fields in SCHEMA_FIELDS.items():
            cols = ["id INT AUTO_INCREMENT PRIMARY KEY", "barcode VARCHAR(255)"]
            for n, _ in fields:
                cols.append(f"{n} TEXT")
            sql = f"CREATE TABLE IF NOT EXISTS {tbl} ({', '.join(cols)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
            self._execute(sql)

        self._commit()
        print("🧱 数据表检查/创建完成")

    # ---------- 业务逻辑 ----------
    def ensure_barcode(self, barcode):
        if not self.connected:
            return
        sql = "INSERT IGNORE INTO barcode_master (barcode) VALUES (%s);"
        self._execute(sql, (barcode,))
        self._commit()

    def get_status(self, barcode):
        if not self.connected:
            return (0, 0, 0)
        sql = "SELECT status_1,status_2,status_3 FROM barcode_master WHERE barcode=%s;"
        cur = self._execute(sql, (barcode,))
        row = cur.fetchone() if cur else None
        return tuple(int(x) for x in row) if row else (0, 0, 0)

    def update_status(self, barcode, s1=None, s2=None, s3=None):
        if not self.connected:
            return
        parts, vals = [], []
        if s1 is not None:
            parts.append("status_1=%s")
            vals.append(s1)
        if s2 is not None:
            parts.append("status_2=%s")
            vals.append(s2)
        if s3 is not None:
            parts.append("status_3=%s")
            vals.append(s3)
        if not parts:
            return
        vals.append(barcode)
        sql = f"UPDATE barcode_master SET {', '.join(parts)} WHERE barcode=%s;"
        self._execute(sql, tuple(vals))
        self._commit()

    def insert_table(self, table, barcode, data):
        if not self.connected:
            return
        fields = list(data.keys())
        values = list(data.values())
        ph = ", ".join(["%s"] * len(values))
        sql = f"INSERT INTO {table} (barcode, {', '.join(fields)}) VALUES (%s, {ph});"
        self._execute(sql, tuple([barcode] + values))
        self._commit()

    def fetch_table(self, table, barcode):
        if not self.connected:
            return {}
        fields = [n for n, _ in SCHEMA_FIELDS[table]]
        sql = f"SELECT {', '.join(fields)} FROM {table} WHERE barcode=%s;"
        cur = self._execute(sql, (barcode,))
        row = cur.fetchone()
        return dict(zip(fields, row)) if row else {}

    def fetch_overview(self):
        cur = self._execute("SELECT barcode FROM barcode_master;")
        if cur is None:
            return []  # 数据库未连接或 SQL 执行失败，直接返回空列表

        barcodes = [r[0] for r in cur.fetchall()]
        result = []
        for bc in barcodes:
            s1, s2, s3 = self.get_status(bc)
            total = self._calc_total_status(bc, s1, s2, s3)
            result.append((bc, s1, s2, s3, total))
        return result  # 记得返回 result

    def _calc_total_status(self, barcode, s1, s2, s3):
        if not all([s1, s2, s3]):
            return "未完成"
        for tbl in SCHEMA_FIELDS:
            data = self.fetch_table(tbl, barcode)
            for v in data.values():
                if str(v).strip().upper() == "NG":
                    return "NG"
        return "OK"

    def close(self):
        if self.conn:
            self.conn.close()
            self.connected = False
            print("🔌 数据库连接已关闭。")

    def fetch_quality_personnel_history(self):
        personnel = set()
        for tbl in ["table_1_data", "table_2_data", "table_3_data"]:
            cur = self._execute(f"SELECT DISTINCT quality_personnel FROM {tbl} WHERE quality_personnel IS NOT NULL;")
            rows = cur.fetchall()
            personnel.update([row[0] for row in rows if row[0]])
        return list(personnel)
