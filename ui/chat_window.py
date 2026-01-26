# ui/chat_window.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTextBrowser, QTextEdit, QCheckBox,
                               QGraphicsDropShadowEffect, QFrame)
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QColor, QKeyEvent, QTextCursor

from ui.styles import MAIN_STYLES, COLORS
from ui.worker import ChatWorker
from backend.agent import KnowledgeAgent

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

class FlashChatWindow(QWidget):
    def __init__(self, agent: KnowledgeAgent):
        super().__init__()
        self.agent = agent
        self.chat_worker = None
        
        # 窗口拖拽变量
        self._drag_pos = None
        self._resize_edge = 0
        self._resize_start_geom = None
        self._resize_start_pos = None
        self.resize_margin = 10

        self.init_window_properties()
        self.setup_ui()
        self.setStyleSheet(MAIN_STYLES)
        self.setMouseTracking(True) 

    def init_window_properties(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)  # | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # [修改 1] 宽屏尺寸，类似网页版 ChatGPT
        self.resize(900, 650)
        self.setMinimumSize(600, 500)

    def setup_ui(self):
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(10, 10, 10, 10) 

        # 主容器
        self.container = QWidget()
        self.container.setObjectName("Container")
        self.container.setMouseTracking(True)
        self.container.setStyleSheet(f"""
            QWidget#Container {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 5)
        self.container.setGraphicsEffect(shadow)
        self.root_layout.addWidget(self.container)

        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(20, 15, 20, 20)
        self.layout.setSpacing(15)

        # --- 1. 顶部 Header ---
        header_layout = QHBoxLayout()
        title = QLabel("🤖 FlashChat")
        title.setStyleSheet(f"color: {COLORS['text']}; font-weight: bold; font-size: 16px;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"background: transparent; color: {COLORS['placeholder']}; border: none; font-size: 20px;")
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)
        self.layout.addLayout(header_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {COLORS['border']};")
        self.layout.addWidget(line)

        # --- 2. 聊天历史区域 (含悬浮加载条) ---
        # 使用一个容器来叠放 TextBrowser 和 LoadingLabel
        self.chat_area_container = QWidget()
        self.chat_area_layout = QVBoxLayout(self.chat_area_container)
        self.chat_area_layout.setContentsMargins(0, 0, 0, 0)
        
        self.history_view = QTextBrowser()
        self.history_view.setOpenExternalLinks(True)
        self.history_view.setStyleSheet(f"""
            QTextBrowser {{
                background-color: transparent;
                border: none;
                color: {COLORS['text']};
                font-family: "Segoe UI", sans-serif;
                font-size: 15px;
            }}
        """)
        self.chat_area_layout.addWidget(self.history_view)
        
        # [修改 2] 显眼的加载提示 (悬浮在聊天框中央)
        self.loading_overlay = QLabel("✨ AI 正在思考中...", self.history_view)
        self.loading_overlay.setAlignment(Qt.AlignCenter)
        self.loading_overlay.hide() # 默认隐藏
        self.loading_overlay.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['accent']};
                color: #202124;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }}
        """)
        
        self.layout.addWidget(self.chat_area_container)

        # --- 3. 工具栏 ---
        tools_layout = QHBoxLayout()
        tools_layout.setContentsMargins(0, 5, 0, 0)

        self.kb_check = QCheckBox(" 🔌 启用知识库检索")
        self.kb_check.setCursor(Qt.PointingHandCursor)
        self.kb_check.setObjectName("KBCheckBox") 
        self.kb_check.setToolTip("开启后，AI 将先检索您的笔记，再回答问题")
        
        tools_layout.addWidget(self.kb_check)
        tools_layout.addStretch()

        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(f"background: transparent; color: {COLORS['placeholder']}; border: none;")
        clear_btn.clicked.connect(self.clear_history)
        tools_layout.addWidget(clear_btn)
        
        self.layout.addLayout(tools_layout)

        # --- 4. 输入区域 ---
        input_container = QHBoxLayout()
        input_container.setSpacing(10)

        self.input_edit = QTextEdit()
        self.input_edit.setFixedHeight(60) 
        self.input_edit.setPlaceholderText("在这里输入问题 (Enter 发送)...")
        self.input_edit.installEventFilter(self)
        self.input_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['input_bg']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 10px 15px;
                color: {COLORS['text']};
                font-size: 14px;
            }}
            QTextEdit:focus {{ border: 1px solid {COLORS['accent']}; }}
        """)
        input_container.addWidget(self.input_edit)
        
        self.send_btn = QPushButton("➤")
        self.send_btn.setFixedSize(40, 40)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']}; color: #202124;
                border-radius: 20px; font-size: 18px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #AECBFA; }}
            QPushButton:disabled {{ background-color: {COLORS['border']}; }}
        """)
        self.send_btn.clicked.connect(self.send_message)
        input_container.addWidget(self.send_btn)
        
        self.layout.addLayout(input_container)

    # --- 逻辑功能 ---

    def toggle_window(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()
            self.input_edit.setFocus()

    def send_message(self):
        text = self.input_edit.toPlainText().strip()
        if not text: return

        self.append_message("User", text)
        self.input_edit.clear()
        
        self.input_edit.setReadOnly(True)
        self.send_btn.setEnabled(False)
        
        # [修改] 显示加载悬浮窗，并手动居中
        self.show_loading()
        
        # 记录本次发送的状态，以便回调时使用
        self.last_use_kb = self.kb_check.isChecked()
        
        self.chat_worker = ChatWorker(self.agent, text, self.last_use_kb)
        self.chat_worker.response_signal.connect(self.on_response)
        self.chat_worker.start()

    def show_loading(self):
        """显示并居中加载条"""
        self.loading_overlay.adjustSize()
        # 计算居中位置
        parent_rect = self.history_view.geometry()
        x = parent_rect.width() / 2 - self.loading_overlay.width() / 2
        y = parent_rect.height() / 2 - self.loading_overlay.height() / 2
        self.loading_overlay.move(int(x), int(y))
        self.loading_overlay.show()
        self.loading_overlay.raise_()

    def on_response(self, response_text, is_error):
        self.loading_overlay.hide() # 隐藏加载条
        
        self.input_edit.setReadOnly(False)
        self.send_btn.setEnabled(True)
        self.input_edit.setFocus()

        role = "Error" if is_error else "AI"
        
        # [修改 3] 传递 use_kb 状态给 append_message
        self.append_message(role, response_text, is_kb_mode=self.last_use_kb)

    def append_message(self, role, text, is_kb_mode=False):
        """
        :param role: User / AI / Error
        :param text: 内容
        :param is_kb_mode: 本次是否使用了知识库 (仅当 role=AI 时有效)
        """
        is_user = (role == "User")
        
        if is_user:
            bg_color = COLORS['accent'] 
            text_color = "#202124" 
            align = "right"
            role_name = "You"
            role_color = COLORS['placeholder']
            border_radius = "15px 15px 0 15px"
        elif role == "Error":
            bg_color = "#FF6B6B"
            text_color = "white"
            align = "left"
            role_name = "System Error"
            role_color = "#FF6B6B"
            border_radius = "15px 15px 15px 0"
        else:
            # AI
            bg_color = "#3A3B3E"
            text_color = COLORS['text']
            align = "left"
            
            # [修改 3] 动态显示名字
            if is_kb_mode:
                role_name = "AI (Knowledge Base)"
                # 可以给 Knowledge Base 加个颜色高亮
                # role_name_html = f"AI <span style='color:{COLORS['success']}'> (Knowledge Base)</span>"
            else:
                role_name = "AI"
                
            role_color = COLORS['accent']
            border_radius = "15px 15px 15px 0" 

        if HAS_MARKDOWN and role == "AI":
            content_html = markdown.markdown(text, extensions=['fenced_code', 'nl2br'])
        else:
            content_html = text.replace('\n', '<br>')

        html = f"""
        <div style="width: 100%; display: block; margin-bottom: 20px; overflow: hidden;">
            <div style="width: 100%; text-align: {align};">
                <div style="font-size: 12px; color: {role_color}; margin-bottom: 4px; font-weight: bold;">
                    {role_name}
                </div>
                <div style="
                    display: inline-block; 
                    background-color: {bg_color}; 
                    color: {text_color}; 
                    padding: 10px 14px; 
                    border-radius: {border_radius}; 
                    text-align: left;
                    max-width: 85%;
                    word-wrap: break-word;
                ">
                    {content_html}
                </div>
            </div>
        </div>
        <br>
        """
        
        self.history_view.moveCursor(QTextCursor.MoveOperation.End)
        self.history_view.insertHtml(html)
        self.history_view.moveCursor(QTextCursor.MoveOperation.End)

    def clear_history(self):
        self.history_view.clear()
        self.agent.clear_history()

    # --- 保持 Resize 时 Loading 条居中 ---
    def resizeEvent(self, event):
        if self.loading_overlay.isVisible():
            self.show_loading() # 重新计算位置
        super().resizeEvent(event)

    # --- 事件处理 ---

    def eventFilter(self, obj, event):
        if obj == self.input_edit and event.type() == QKeyEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self.send_message()
                return True
        return super().eventFilter(obj, event)

    def _calc_edge(self, pos: QPoint) -> int:
        edge = 0
        r = self.rect()
        margin = self.resize_margin
        if pos.x() < margin: edge |= 1
        elif pos.x() > r.width() - margin: edge |= 4
        if pos.y() < margin: edge |= 2
        elif pos.y() > r.height() - margin: edge |= 8
        return edge

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edge = self._calc_edge(event.pos())
            if edge != 0:
                self._resize_edge = edge
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geom = self.geometry()
            else:
                self._resize_edge = 0
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._resize_edge != 0:
            curr_pos = event.globalPosition().toPoint()
            diff = curr_pos - self._resize_start_pos
            geom = QRect(self._resize_start_geom)
            if self._resize_edge & 1: geom.setLeft(geom.left() + diff.x())
            if self._resize_edge & 4: geom.setRight(geom.right() + diff.x())
            if self._resize_edge & 2: geom.setTop(geom.top() + diff.y())
            if self._resize_edge & 8: geom.setBottom(geom.bottom() + diff.y())
            if geom.width() >= self.minimumWidth() and geom.height() >= self.minimumHeight():
                self.setGeometry(geom)
        elif self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_edge = 0
        event.accept()