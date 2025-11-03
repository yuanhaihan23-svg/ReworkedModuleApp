import pandas as pd
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox,QComboBox,
                             QSplitter, QTextEdit, QFileDialog, QLineEdit,
                             QSizePolicy, QCompleter)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from openpyxl.styles import PatternFill
from db import DB
from config import SCHEMA_FIELDS

# ----------------------------
# GUI CLASS
# ----------------------------
class BarcodeApp(QWidget):
    def __init__(self):
        super().__init__()
        self.db = DB()
        self.current_barcode = None
        self.current_table = None
        self.session_barcodes = set()  # 本次运行的条码集合

        # ----------------------
        # 窗口 & 总布局
        # ----------------------
        self.setWindowTitle("Rework Module Status Filling System")
        self.setGeometry(100, 50, 1400, 700)
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Barcode 输入行
        hbox = QHBoxLayout()
        layout.addLayout(hbox)

        # 标签
        hbox.addWidget(QLabel("Barcode:"))

        # 条码输入框
        self.barcode_edit = QLineEdit()
        self.barcode_edit.setFocus()
        self.barcode_edit.returnPressed.connect(self.scan_barcode)

        # 设置输入框随窗口横向拉伸，并指定最小宽度
        self.barcode_edit.setMinimumWidth(400)  # 最小宽度，可根据需求调大
        self.barcode_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        hbox.addWidget(self.barcode_edit)

        # Scan 按钮
        scan_btn = QPushButton("Enter")
        scan_btn.clicked.connect(self.scan_barcode)
        hbox.addWidget(scan_btn)

        # ----------------------
        # 分割布局：左侧表单 / 右侧 overview + detail
        # ----------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # 左侧表单
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        splitter.addWidget(left_widget)

        # 表格占据剩余空间
        self.form_table = QTableWidget()
        left_layout.addWidget(self.form_table, stretch=1)  # stretch=1 表示表格拉伸填满剩余空间

        # 提交按钮固定高度
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.clicked.connect(self.submit_form)
        self.submit_btn.setEnabled(False)
        self.submit_btn.setFixedHeight(40)  # 可以根据需求调整高度
        left_layout.addWidget(self.submit_btn)  # stretch=0 默认固定高度

        # ----------------------
        # 右侧 Overview + Detail
        # ----------------------
        right_layout = QVBoxLayout()
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        # Overview 表格
        self.overview_table = QTableWidget()
        self.overview_table.setColumnCount(5)
        self.overview_table.setHorizontalHeaderLabels([
            "Barcode", "表1_模组拆解状态", "表2_CMM测试状态", "表3_模组配对状态", "总状态"
        ])
        # 按照扫码时间降序排列overview栏
        self.barcode_scan_time = {}  # {barcode: datetime对象}

        # 列宽控制：前 4 列可调节，最后一列自适应填满
        header = self.overview_table.horizontalHeader()
        for i in range(4):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        # 可选：允许用户拖拽调整列顺序
        header.setSectionsMovable(True)

        self.overview_table.cellClicked.connect(self.show_detail)
        right_layout.addWidget(self.overview_table)

        # ----------------------
        # 按钮区（刷新 / 导出）
        # ----------------------
        btn_box = QHBoxLayout()
        right_layout.addLayout(btn_box)

        refresh_btn = QPushButton("Refresh Overview")
        refresh_btn.clicked.connect(self.load_overview)
        btn_box.addWidget(refresh_btn)

        export_btn = QPushButton("Export Excel")
        export_btn.clicked.connect(self.export_excel_colored)
        btn_box.addWidget(export_btn)

        # ----------------------
        # Detail 显示区域
        # ----------------------
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        right_layout.addWidget(self.detail_text)

        # ----------------------
        # 初始化界面
        # ----------------------
        self.setup_ui()
        self.overview_table.setRowCount(0)
        self._apply_table_adjustments()

    # ----------------------
    # 自动调整行高
    # ----------------------
    def adjust_table_rows(self, table: QTableWidget):
        """根据内容自动调整行高"""
        table.resizeRowsToContents()

    # ----------------------
    # 左侧表单表格调整
    # ----------------------
    def adjust_form_table(self):
        """调整左侧表单表格列宽（标签列宽，值列窄）"""
        table = self.form_table
        if table.columnCount() == 0:
            return

        table_width = table.viewport().width()
        label_col_width = int(table_width * 0.75)
        value_col_width = table_width - label_col_width

        table.setColumnWidth(0, label_col_width)
        table.setColumnWidth(1, value_col_width)
        self.adjust_table_rows(table)

    # ----------------------
    # 右侧 overview 表格调整
    # ----------------------
    def adjust_overview_table(self):
        """调整右侧 Overview 表格列宽（条码宽，状态列略窄，总状态略宽）"""
        table = self.overview_table
        if table.columnCount() == 0:
            return

        total_width = table.viewport().width()
        proportions = [3, 1.2, 1.2, 1.2, 1]  # 可微调
        total_ratio = sum(proportions)

        for i, ratio in enumerate(proportions):
            col_width = int(total_width * ratio / total_ratio)
            table.setColumnWidth(i, col_width)

        self.adjust_table_rows(table)

    # ----------------------
    # 窗口大小变化时触发优化布局
    # ----------------------
    def resizeEvent(self, event):
        """根据窗口大小自动调整两侧表格的列宽与行高"""
        super().resizeEvent(event)

        # 使用 QTimer 防抖，避免频繁触发时卡顿或闪烁
        if hasattr(self, "_resize_timer"):
            self._resize_timer.stop()
        else:
            from PyQt6.QtCore import QTimer
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._apply_table_adjustments)

        self._resize_timer.start(100)  # 100ms 后调整，防止频繁调用

    def _apply_table_adjustments(self):
        """执行表格调整"""
        self.adjust_form_table()
        self.adjust_overview_table()

    def setup_ui(self):
        # 界面初始化代码
        pass

    def add_overview(self, status):
        if not self.current_barcode:
            QMessageBox.warning(self, "Warning", "Please scan a barcode first!")
            return
        # 保存到数据库
        self.db.add_overview(self.current_barcode, status)
        # 添加到 Overview 表格
        row_position = self.overview_table.rowCount()
        self.overview_table.insertRow(row_position)
        self.overview_table.setItem(row_position, 0, QTableWidgetItem(self.current_barcode))
        self.overview_table.setItem(row_position, 1, QTableWidgetItem(status))
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.overview_table.setItem(row_position, 2, QTableWidgetItem(timestamp))
        self.current_barcode = None  # 重置当前条码

    # ---------- 核心逻辑 ----------
    def scan_barcode(self):
        code = self.barcode_edit.text().strip()
        if not code:
            return

        # 校验条码长度
        if len(code) != 24:
            QMessageBox.warning(self, "无效条码", "条码必须为 24 位！")
            self.barcode_edit.clear()
            return

        self.current_barcode = code
        self.session_barcodes.add(code)
        from datetime import datetime
        self.barcode_scan_time[code] = datetime.now()

        # 确保数据库中有 overview 记录（如果没有则新建）
        self.db.ensure_barcode(code)

        # 实时检查每个子表是否存在
        has_t1 = bool(self.db.fetch_table("table_1_data", code))
        has_t2 = bool(self.db.fetch_table("table_2_data", code))
        has_t3 = bool(self.db.fetch_table("table_3_data", code))

        # 根据当前缺少的表单，自动决定要填写哪个
        if not has_t1:
            self.current_table = "table_1_data"
        elif not has_t2:
            self.current_table = "table_2_data"
        elif not has_t3:
            self.current_table = "table_3_data"
        else:
            self.current_table = None

        # 如果该条码已全部完成，则提示
        if not self.current_table:
            QMessageBox.information(self, "提示", f"条码 {code} 的所有表单均已完成。")
            self.form_table.setRowCount(0)
            self.submit_btn.setEnabled(False)
            return

        # 载入表单和 Overview
        self.load_form()
        self.load_overview()

    def load_form(self):
        self.form_table.clear()
        if not self.current_table:
            self.form_table.setRowCount(0); self.form_table.setColumnCount(0)
            self.detail_text.setText(f"{self.current_barcode} 已完成所有表单")
            self.submit_btn.setEnabled(False)
            return
        self.submit_btn.setEnabled(True)
        fields = SCHEMA_FIELDS[self.current_table]
        self.form_table.setRowCount(len(fields)); self.form_table.setColumnCount(2)
        self.form_table.setHorizontalHeaderLabels(["检查项目","状态 (OK / NG)"])

        for i, (name, _) in enumerate(fields):
            label = self.get_label(self.current_table, name)
            self.form_table.setItem(i, 0, QTableWidgetItem(label))

            if name == "timestamp":
                # 自动时间
                item = QTableWidgetItem(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.form_table.setItem(i, 1, item)

            elif name == "quality_personnel":
                # 用 QLineEdit + 自动补全功能
                edit = QLineEdit()
                edit.setPlaceholderText("请输入工号")

                # 从数据库加载历史工号
                history = self.db.fetch_quality_personnel_history()

                if history:
                    completer = QCompleter(history)
                    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # 不区分大小写
                    completer.setFilterMode(Qt.MatchFlag.MatchContains)  # 支持模糊匹配
                    edit.setCompleter(completer)
                self.form_table.setCellWidget(i, 1, edit)

            else:
                # OK/NG 下拉框
                combo = QComboBox()
                combo.addItems(["OK", "NG"])
                self.form_table.setCellWidget(i, 1, combo)
        self._apply_table_adjustments()

    def submit_form(self):
        if not self.current_table or not self.current_barcode:
            QMessageBox.warning(self, "错误", "当前没有可提交的表格")
            return

        # 校验表单完整性
        missing_fields = []
        data = {}

        for i, (name, _) in enumerate(SCHEMA_FIELDS[self.current_table]):
            if name == "timestamp":
                data[name] = self.form_table.item(i, 1).text()
                continue

            widget = self.form_table.cellWidget(i, 1)
            value = ""
            if isinstance(widget, QComboBox):
                value = widget.currentText().strip()
            elif isinstance(widget, QLineEdit):
                value = widget.text().strip()
            elif self.form_table.item(i, 1):
                value = self.form_table.item(i, 1).text().strip()

            # 记录数据
            data[name] = value

            # 检查是否为空
            if not value:
                missing_fields.append(self.get_label(self.current_table, name))

                # 高亮显示未填写的单元格
                if widget:
                    widget.setStyleSheet("background-color: #ffcccc;")
                else:
                    item = self.form_table.item(i, 1)
                    if item:
                        item.setBackground(QColor(255, 200, 200))
            else:
                # 恢复正常背景色
                if widget:
                    widget.setStyleSheet("")
                else:
                    item = self.form_table.item(i, 1)
                    if item:
                        item.setBackground(QColor(255, 255, 255))

        # 如果有未填项，则提醒用户并终止提交
        if missing_fields:
            QMessageBox.warning(
                self,
                "未填写提示",
                "以下项目未填写，请补全后再提交：\n\n" + "\n".join(missing_fields)
            )
            return

        # 通过校验后再执行原有逻辑
        self.db.insert_table(self.current_table, self.current_barcode, data)
        if self.current_table == "table_1_data":
            self.db.update_status(self.current_barcode, s1=1)
        elif self.current_table == "table_2_data":
            self.db.update_status(self.current_barcode, s2=1)
        elif self.current_table == "table_3_data":
            self.db.update_status(self.current_barcode, s3=1)

        QMessageBox.information(self, "提交成功", f"{self.get_table_name(self.current_table)} 已完成")
        self.load_overview()

        # 清空当前条码，让按钮恢复可用状态
        self.current_barcode = None
        self.current_table = None
        self.barcode_edit.clear()
        self.barcode_edit.setFocus()
        self.form_table.setRowCount(0)
        self.submit_btn.setEnabled(False)
        self.detail_text.clear()

    def load_overview(self):
        """根据数据库中实际的子表数据实时计算 Overview 状态"""
        try:
            if not self.session_barcodes:
                self.overview_table.setRowCount(0)
                return

            # 清空表格
            self.overview_table.setRowCount(0)

            # 按扫码时间降序排序（最近扫描的在最上方）
            barcodes_sorted = sorted(
                self.session_barcodes,
                key=lambda b: self.barcode_scan_time.get(b, datetime.min),
                reverse=True
            )

            for barcode in sorted(self.session_barcodes):
                # 检查三个分表数据
                t1_data = self.db.fetch_table("table_1_data", barcode)
                t2_data = self.db.fetch_table("table_2_data", barcode)
                t3_data = self.db.fetch_table("table_3_data", barcode)

                s1 = 1 if t1_data else 0
                s2 = 1 if t2_data else 0
                s3 = 1 if t3_data else 0

                # 计算总状态：
                # 如果三个表都完成，并且所有字段均为 OK → OK
                # 否则，如果有 NG → NG
                # 否则 → 未完成
                total_status = "未完成"
                if s1 and s2 and s3:
                    all_vals = []
                    for data in (t1_data, t2_data, t3_data):
                        if data:
                            all_vals.extend(list(data.values()))
                    if any(str(v).upper() == "NG" for v in all_vals):
                        total_status = "NG"
                    else:
                        total_status = "OK"

                # 写入表格
                row = self.overview_table.rowCount()
                self.overview_table.insertRow(row)

                # 条码
                barcode_item = QTableWidgetItem(barcode)
                barcode_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.overview_table.setItem(row, 0, barcode_item)

                # 三个子表状态
                for j, val in enumerate([s1, s2, s3]):
                    text = "已完成" if val else "未完成"
                    color = QColor(0, 200, 83) if val else QColor(255, 77, 77)
                    item = QTableWidgetItem(text)
                    item.setBackground(QBrush(color))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                    self.overview_table.setItem(row, j + 1, item)

                # 总状态
                total_item = QTableWidgetItem(total_status)
                total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if total_status == "OK":
                    c = QColor(46, 204, 113)
                elif total_status == "NG":
                    c = QColor(231, 76, 60)
                else:
                    c = QColor(200, 200, 200)
                total_item.setBackground(QBrush(c))
                total_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.overview_table.setItem(row, 4, total_item)

            self._apply_table_adjustments()

        except Exception as e:
            QMessageBox.critical(self, "刷新失败", f"加载 Overview 时出错：\n{str(e)}")

    # ---------- Detail 显示带颜色 ----------
    def show_detail(self,row,col):
        if row<0: return
        barcode=self.overview_table.item(row,0).text()
        html=f"<h2>Barcode: {barcode}</h2>"
        for tbl in SCHEMA_FIELDS:
            html+=f"<h3>{self.get_table_name(tbl)}</h3>"
            data=self.db.fetch_table(tbl,barcode)
            if not data:
                html+="<p><i>未填写</i></p>"
            else:
                html+="<table border='0' cellspacing='3' cellpadding='3'>"
                for k,v in data.items():
                    label=self.get_label(tbl,k)
                    val=str(v).strip()
                    color="#FF4C4C" if val.upper()=="NG" else "#2ECC71" if val.upper()=="OK" else "#000"
                    html+=f"<tr><td>{label}</td><td><b><font color='{color}'>{val}</font></b></td></tr>"
                html+="</table>"
            html+="<hr>"
        self.detail_text.setHtml(html)

    # ----------------------------
    # EXPORT EXCEL
    # ----------------------------
    def export_excel_colored(self):
        """导出当前 Overview 表格中显示的条码及对应的所有分表详细数据"""
        try:
            row_count = self.overview_table.rowCount()
            if row_count == 0:
                QMessageBox.warning(self, "无数据", "当前表格中没有可导出的数据！")
                return

            # 选择保存路径
            default_name = f"current_detail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "选择保存位置", default_name, "Excel 文件 (*.xlsx)"
            )
            if not file_path:
                return

            # 提取当前 Overview 表格中所有条码
            barcodes = [self.overview_table.item(i, 0).text() for i in range(row_count)]

            # 从数据库获取 overview 数据
            all_rows = self.db.fetch_overview()
            rows = [r for r in all_rows if r[0] in barcodes]
            merged_df = pd.DataFrame(rows, columns=["barcode", "表1状态", "表2状态", "表3状态", "总状态"])

            # 合并所有分表
            for tbl, fields in SCHEMA_FIELDS.items():
                col_names = [f[0] for f in fields]
                cur = self.db._execute(f"SELECT barcode,{','.join(col_names)} FROM {tbl};")
                rows = cur.fetchall()
                df = pd.DataFrame(rows, columns=["barcode"] + col_names)
                merged_df = pd.merge(merged_df, df, on="barcode", how="left")

            # 只保留当前表格显示的条码
            merged_df = merged_df[merged_df["barcode"].isin(barcodes)]

            # 写入 Excel
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                merged_df.to_excel(writer, sheet_name="当前表格数据", index=False)
                ws = writer.sheets["当前表格数据"]

                # 定义颜色
                red_fill = PatternFill(start_color="FF9999", end_color="FF9999", fill_type="solid")
                green_fill = PatternFill(start_color="99FF99", end_color="99FF99", fill_type="solid")
                gray_fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

                # 给单元格上色
                for row in range(2, len(merged_df) + 2):
                    for col in range(2, merged_df.shape[1] + 1):
                        cell = ws.cell(row=row, column=col)
                        val = str(cell.value).upper() if cell.value else ""
                        if val in ["NG", "未完成"]:
                            cell.fill = red_fill
                        elif val in ["OK", "已完成"]:
                            cell.fill = green_fill
                        elif not val:
                            cell.fill = gray_fill

            QMessageBox.information(self, "导出成功", f"已导出当前表格及详细数据：\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出 Excel 时发生错误：\n{str(e)}")

    # ---------- Label 辅助 ----------
    def get_table_name(self,tbl):
        return {
            "table_1_data":"表1_模组拆解状态",
            "table_2_data":"表2_CMM测试状态",
            "table_3_data":"表3_模组配对状态"
        }.get(tbl,tbl)

    def get_label(self, tbl, field):
        labels = {
            "table_1_data": {
                "timestamp": "时间",
                "quality_personnel": "品质人员-Quality",
                "protective_cover_installation_status": "正负极保护盖已安装-Positive and negative protective covers installed",
                "protective_cover_appearance_status": "正负极连接铜排无破损，无异物-No damage or foreign matters on the positive and negative copper bar",
                "FPC_appearance_status": "FPC/卡扣无破损无脏污-No damage or foreign matters on FPC or buckles ",
                "FPC_foreign_matters_status": "FPC插接口无破损无脏污-No damage or foreign matters on FPC plug",
                "end_plate_hole_appearance_status": "端板孔无破损-No damage on end plate hole",
                "insulation_sheet_appearance_status": "端板上下绝缘片无破损-No damage on insulation",
                "side_plate_foam_appearance_status": "侧板缓冲棉清洁清洁-Clean of side plate cushion foam",
                "side_plate_appearance_status": "侧板与吊耳无划伤，无破损及变形-No scratch, damage or deformation on side plate and lugs",
                "bottom_glue_clean_status": "模组底部残胶无残留-No residue glue on module bottom",
                "module_bottom_picture": "模组底部照片-Module bottom pictures",
                "tray_foam_status": "托盘及缓冲泡棉无异物-No foreign matters on tray and cushion foam",
                "module_code_status": "模组码无破损脏污-No damage or dirty on module code",
                "module_hi_pot_test_status": "模组耐压数据-Module hi-pot test"
            },
            "table_2_data": {
                "timestamp": "时间",
                "quality_personnel": "品质人员-Quality",
                "module_CMMtest_status": "模组全尺寸测量-Module CMM test"
            },
            "table_3_data": {
                "module_CMMtest_status": "模组全尺寸测量-Module CMM test",
                "timestamp": "时间",
                "quality_personnel": "品质人员-Quality",
                "voltage_status_consistent": "模组电压区间/充电未充电一致-Module voltage range/distinction between charging and uncharging",
                "cell_batch_consistent": "电芯批次一致-Cell batch consistency",
                "module_grade_consistent": "模组档位一致-Module grade consistency",
                "module_unbound_status": "模组已解绑-Module already unbounded"
            }
        }
        return labels.get(tbl, {}).get(field, field)