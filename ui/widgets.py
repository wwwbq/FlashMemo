# ui/widgets.py

from PySide6.QtWidgets import (QWidget, QPlainTextEdit, QTextBrowser, QComboBox, 
                               QLineEdit, QStackedLayout, QToolButton, QHBoxLayout, 
                               QVBoxLayout, QSplitter, QPushButton, QLabel)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import (QKeyEvent, QPixmap, QPainter, QColor, 
                           QPen, QIcon, QPainterPath, QFont)

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

from ui.styles import COLORS
from ui.highlighter import MarkdownHighlighter

class NoteEditor(QWidget):
    """
    [重构] 支持 Markdown 实时预览和高亮的编辑器组件
    结构：Toolbar + (Editor | Preview) Splitter
    """
    save_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        # --- 1. 工具栏 (包含预览开关) ---
        tools_layout = QHBoxLayout()
        tools_layout.setContentsMargins(0, 0, 0, 0)
        
        self.preview_btn = QPushButton("👁️ 预览")
        self.preview_btn.setCheckable(True)
        self.preview_btn.setChecked(True) # 默认开启预览
        self.preview_btn.setCursor(Qt.PointingHandCursor)
        self.preview_btn.setFixedSize(60, 24)
        self.preview_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['input_bg']}; color: {COLORS['placeholder']}; 
                border: 1px solid {COLORS['border']}; border-radius: 4px; font-size: 12px;
            }}
            QPushButton:checked {{
                background: {COLORS['accent']}; color: #202124; border: 1px solid {COLORS['accent']}; font-weight: bold;
            }}
        """)
        self.preview_btn.toggled.connect(self.toggle_preview)
        
        tools_layout.addStretch()
        tools_layout.addWidget(self.preview_btn)
        self.layout.addLayout(tools_layout)

        # --- 2. 分割器 (Splitter) ---
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(2) # 拖拽条宽度
        # 设置分割条样式
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLORS['border']};
            }}
        """)

        # --- 左侧：纯文本编辑器 ---
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("在此输入 Markdown 内容...")
        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS['input_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px;
                color: {COLORS['text']};
                font-family: "Consolas", "Microsoft YaHei", monospace;
                font-size: 14px;
            }}
            QPlainTextEdit:focus {{ border: 1px solid {COLORS['accent']}; }}
        """)
        # 绑定高亮器
        self.highlighter = MarkdownHighlighter(self.editor.document())
        # 拦截快捷键
        self.editor.installEventFilter(self)
        
        # --- 右侧：HTML 预览器 ---
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.preview.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px;
                color: {COLORS['text']};
            }}
        """)

        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.preview)
        
        # 设置默认比例 1:1
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        
        self.layout.addWidget(self.splitter)

        # --- 3. 防抖定时器 ---
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True) # 只触发一次
        self.render_timer.setInterval(500)    # 500ms 延迟
        self.render_timer.timeout.connect(self.render_markdown)
        
        # 监听输入变化
        self.editor.textChanged.connect(self.on_text_changed)

    def on_text_changed(self):
        # 每次输入重置定时器，实现防抖
        self.render_timer.start()

    def render_markdown(self):
        """将 Markdown 转为 HTML 显示在预览区"""
        text = self.editor.toPlainText()
        if HAS_MARKDOWN:
            html = markdown.markdown(text, extensions=['fenced_code', 'nl2br', 'tables'])
            # 简单的 CSS 修复
            html = f"<style>code {{ background-color: #3A3B3E; padding: 2px; border-radius: 3px; }}</style>{html}"
            self.preview.setHtml(html)
        else:
            self.preview.setPlainText(text)

    def toggle_preview(self, checked):
        self.preview.setVisible(checked)

    # --- 兼容旧接口 ---
    
    def toPlainText(self) -> str:
        return self.editor.toPlainText()

    def setPlainText(self, text: str):
        self.editor.setPlainText(text)
        # 手动触发一次渲染，不用等待
        self.render_markdown()

    def setPlaceholderText(self, text: str):
        self.editor.setPlaceholderText(text)

    def setReadOnly(self, ro: bool):
        self.editor.setReadOnly(ro)

    def textCursor(self):
        return self.editor.textCursor()

    def setTextCursor(self, cursor):
        self.editor.setTextCursor(cursor)

    def eventFilter(self, obj, event):
        if obj == self.editor and event.type() == QKeyEvent.KeyPress:
            if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Return:
                self.save_signal.emit()
                return True
        return super().eventFilter(obj, event)

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