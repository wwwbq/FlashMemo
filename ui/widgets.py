# ui/widgets.py

from PySide6.QtWidgets import (QWidget, QTextEdit, QComboBox, QLineEdit, 
                               QStackedLayout, QToolButton, QHBoxLayout)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import (QKeyEvent, QPixmap, QPainter, QColor, 
                           QPen, QIcon, QPainterPath, QFont)

from ui.styles import COLORS

class NoteEditor(QTextEdit):
    save_signal = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("在此输入笔记内容 (支持 Markdown)...")
        self.setAcceptRichText(False)
    def keyPressEvent(self, event: QKeyEvent):
        if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Return:
            self.save_signal.emit()
        else:
            super().keyPressEvent(event)

class TagSelector(QWidget):
    # 增加一个信号，当下拉框选中项改变时发射 (用于续写模式联动)
    tag_selected_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QStackedLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # --- 控件 1: 只读下拉框 ---
        self.combo = QComboBox()
        self.combo.setEditable(False)
        self.combo.setPlaceholderText("请选择标签...")
        self.combo.activated.connect(self.on_combo_selected)
        
        # --- 控件 2: 文本输入框 ---
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("请输入标签 (按空格分隔)...")
        
        # 回退按钮
        self.back_btn = QToolButton(self.line_edit)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setToolTip("点击回退到列表")
        fixed_font = QFont()
        fixed_font.setPointSize(10) 
        self.back_btn.setFont(fixed_font)
        
        high_res_icon = self._create_arrow_icon(COLORS['placeholder'])
        self.back_btn.setIcon(high_res_icon)
        self.back_btn.setIconSize(QSize(16, 16)) 
        
        self.back_btn.setStyleSheet("""
            QToolButton { border: none; background: transparent; }
            QToolButton:hover { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
        """)
        self.back_btn.clicked.connect(self.revert_to_combo)

        btn_layout = QHBoxLayout(self.line_edit)
        btn_layout.setContentsMargins(0, 0, 5, 0) 
        btn_layout.addStretch()
        btn_layout.addWidget(self.back_btn)
        self.line_edit.setTextMargins(0, 0, 25, 0) 
        
        self.layout.addWidget(self.combo)
        self.layout.addWidget(self.line_edit)
        self.CUSTOM_OPTION_TEXT = "✏️ 自定义标签 (输入新标签)..."

    def _create_arrow_icon(self, color_hex: str) -> QIcon:
        canvas_size = 64
        pixmap = QPixmap(canvas_size, canvas_size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        center = canvas_size / 2
        offset = 12 
        height = 8  
        path.moveTo(center - offset, center - height)
        path.lineTo(center, center + height)
        path.lineTo(center + offset, center - height)
        pen = QPen(QColor(color_hex))
        pen.setWidth(6) 
        pen.setCapStyle(Qt.RoundCap) 
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.end()
        return QIcon(pixmap)

    def refresh_tags(self, tags: list[str]):
        self.combo.clear()
        if tags: self.combo.addItems(tags)
        self.combo.addItem(self.CUSTOM_OPTION_TEXT)
        self.show_combo_mode()

    def show_combo_mode(self):
        self.combo.setCurrentIndex(-1)
        self.layout.setCurrentIndex(0)

    def show_input_mode(self, initial_text: str = ""):
        self.layout.setCurrentIndex(1)
        self.line_edit.setText(initial_text)
        self.line_edit.setFocus()
        if initial_text: self.line_edit.end(False)

    def revert_to_combo(self):
        self.show_combo_mode()
        self.combo.showPopup()

    def on_combo_selected(self, index):
        text = self.combo.itemText(index)
        # 发射选中信号
        self.tag_selected_signal.emit(text)
        
        if text == self.CUSTOM_OPTION_TEXT:
            self.show_input_mode("")
        else:
            self.show_input_mode(f"{text} ")

    def get_current_tags(self) -> list[str]:
        if self.layout.currentIndex() == 0: return []
        text = self.line_edit.text().strip()
        if not text: return []
        text = text.replace('，', ' ').replace(',', ' ')
        return [t for t in text.split(' ') if t.strip()]

    def force_combo_selection(self):
        """强制切换回 Combo 模式（用于续写模式）"""
        self.show_combo_mode()

# --- [新增] 文件选择器 ---
class FileSelector(QComboBox):
    # 信号: 选中了某个文件ID
    file_selected_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("请选择要续写的笔记...")
        # 样式复用 QComboBox
        self.currentIndexChanged.connect(self.on_changed)

    def update_files(self, file_list: list):
        """
        更新文件列表
        :param file_list: [{'id': '...', 'name': '...'}, ...]
        """
        self.clear()
        self.addItem("请选择笔记...", None) # Placeholder item
        for f in file_list:
            # addItem(text, userData) -> 我们把 ID 存在 UserData 里
            self.addItem(f['name'], f['id'])

    def on_changed(self, index):
        if index < 0: return
        file_id = self.itemData(index)
        if file_id:
            self.file_selected_signal.emit(file_id)