# ui/window.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QGraphicsDropShadowEffect, QApplication, QFrame, QLineEdit)
from PySide6.QtCore import Qt, QPoint, QRect, Signal
from PySide6.QtGui import QColor

from ui.styles import MAIN_STYLES, COLORS
from ui.widgets import NoteEditor, TagSelector, FileSelector 
from ui.sidebar import AISidebar 
from ui.worker import AIWorker, ListFilesWorker, LoadContentWorker 
from backend.entity import Note, NoteType

EDGE_NONE   = 0x0
EDGE_LEFT   = 0x1
EDGE_TOP    = 0x2
EDGE_RIGHT  = 0x4
EDGE_BOTTOM = 0x8

class FlashMemoWindow(QWidget):
    save_requested_signal = Signal(Note)
    update_requested_signal = Signal(Note)
    SIDEBAR_WIDTH = 320 

    def __init__(self, manager, prompts_dir: str):
        super().__init__()
        self.manager = manager
        self.prompts_dir = prompts_dir
        
        self._drag_pos = None           
        self._resize_edge = EDGE_NONE   
        self._resize_start_geom = None  
        self._resize_start_pos = None   
        self.resize_margin = 10 
        
        self.raw_content = ""      
        self.is_refined_mode = False 
        self.ai_worker = None
        self.ai_cache = {} 
        self.current_prompt = ""

        self.is_append_mode = False
        self.current_editing_note_id = None 
        
        self.list_files_worker = None
        self.load_content_worker = None
        
        self.init_window_properties()
        self.setup_ui()
        self.setStyleSheet(MAIN_STYLES)
        self.setMouseTracking(True)

    def init_window_properties(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint )  # 去掉Qt.Tool, 避免mac上点击其他内容窗口会消失 | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(600, 550)
        self.setMinimumSize(400, 350)

    def setup_ui(self):
        self.root_layout = QHBoxLayout(self)
        self.root_layout.setContentsMargins(10, 10, 10, 10) 
        self.root_layout.setSpacing(0) 

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
        
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(20, 15, 20, 20)
        self.content_layout.setSpacing(10)

        self.setup_header() 
        
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("输入标题 (选填，留空自动生成)...")
        self.title_edit.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; color: {COLORS['text']}; 
                border: none; border-bottom: 1px solid {COLORS['border']};
                font-size: 14px; font-weight: bold; padding: 4px;
            }}
            QLineEdit:focus {{ border-bottom: 1px solid {COLORS['accent']}; }}
        """)
        self.content_layout.addWidget(self.title_edit)

        self.editor = NoteEditor()
        self.editor.save_signal.connect(self.request_save)
        self.content_layout.addWidget(self.editor, stretch=1) 
        
        self.setup_tools_area() 
        self.setup_footer() 

        self.sidebar = AISidebar(self.prompts_dir)
        self.sidebar.hide() 
        self.sidebar.run_ai_signal.connect(self.execute_ai_task)

        self.root_layout.addWidget(self.container, stretch=1)
        self.root_layout.addWidget(self.sidebar, stretch=0)

    def setup_header(self):
        header_layout = QHBoxLayout()
        self.status_label = QLabel("FlashMemo")
        self.status_label.setStyleSheet(f"color: {COLORS['placeholder']}; font-weight: bold;")
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLORS['placeholder']}; 
                border: none; font-size: 18px; font-weight: bold;
            }}
            QPushButton:hover {{ color: {COLORS['text']}; }}
        """)
        close_btn.clicked.connect(self.close_window)
        header_layout.addWidget(close_btn)
        
        self.content_layout.addLayout(header_layout)

    def setup_tools_area(self):
        tools_layout = QHBoxLayout()
        
        self.ai_btn = QPushButton("✨ 润色")
        self.ai_btn.setCheckable(True) 
        self.ai_btn.setCursor(Qt.PointingHandCursor)
        self.ai_btn.setFixedHeight(26)
        self.update_ai_btn_style(False)
        self.ai_btn.clicked.connect(self.toggle_sidebar)
        tools_layout.addWidget(self.ai_btn)

        tools_layout.addSpacing(10)

        self.append_switch = QPushButton("📝 续写模式")
        self.append_switch.setCheckable(True)
        self.append_switch.setCursor(Qt.PointingHandCursor)
        self.append_switch.setFixedHeight(26)
        self.append_switch.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['input_bg']}; color: {COLORS['placeholder']}; 
                border: 1px solid {COLORS['border']}; border-radius: 13px; font-size: 12px; padding: 0 10px;
            }}
            QPushButton:checked {{
                background: {COLORS['accent']}; color: #202124; border: 1px solid {COLORS['accent']}; font-weight: bold;
            }}
        """)
        self.append_switch.toggled.connect(self.toggle_append_mode)
        tools_layout.addWidget(self.append_switch)
        
        tools_layout.addStretch() 
        self.content_layout.addLayout(tools_layout)

    def update_ai_btn_style(self, checked):
        if checked: 
            self.ai_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['accent']}; color: #202124; 
                    border: 1px solid {COLORS['accent']}; border-radius: 13px; font-weight: bold; font-size: 12px; padding: 0 10px;
                }}
            """)
        else: 
            self.ai_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['input_bg']}; color: {COLORS['placeholder']}; 
                    border: 1px solid {COLORS['border']}; border-radius: 13px; font-size: 12px; padding: 0 10px;
                }}
                QPushButton:hover {{ border-color: {COLORS['accent']}; color: {COLORS['accent']}; }}
            """)

    def setup_footer(self):
        footer_layout = QHBoxLayout()
        
        self.tag_selector = TagSelector()
        self.tag_selector.tag_selected_signal.connect(self.on_tag_selected_for_append)
        footer_layout.addWidget(self.tag_selector, stretch=3) 
        
        self.file_selector = FileSelector()
        self.file_selector.hide()
        self.file_selector.file_selected_signal.connect(self.on_file_selected)
        footer_layout.addWidget(self.file_selector, stretch=3)

        self.save_btn = QPushButton("保存笔记")
        self.save_btn.setObjectName("SaveBtn") 
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.request_save)
        footer_layout.addWidget(self.save_btn, stretch=1) 
        
        self.content_layout.addLayout(footer_layout)

    def toggle_append_mode(self, checked):
        self.is_append_mode = checked
        if checked:
            self.save_btn.setText("更新笔记")
            self.status_label.setText("Select Tag -> Note to append")
            self.editor.setPlainText("")
            self.editor.setPlaceholderText("请先选择标签和笔记...")
            self.editor.setReadOnly(True)
            self.title_edit.clear()
            self.title_edit.setPlaceholderText("选择笔记后显示标题...")
            self.title_edit.setReadOnly(True) 
            self.file_selector.show()
            self.tag_selector.force_combo_selection()
        else:
            self.save_btn.setText("保存笔记")
            self.status_label.setText("Capture Mode")
            self.editor.setReadOnly(False)
            self.editor.setPlaceholderText("在此输入笔记内容 (支持 Markdown)...")
            self.editor.setPlainText(self.raw_content)
            self.title_edit.setReadOnly(False)
            self.title_edit.clear()
            self.title_edit.setPlaceholderText("输入标题 (选填，留空自动生成)...")
            self.file_selector.hide()
            self.current_editing_note_id = None

    def on_tag_selected_for_append(self, tag_name):
        if not self.is_append_mode or tag_name == self.tag_selector.CUSTOM_OPTION_TEXT: return
        self.status_label.setText(f"Loading files in #{tag_name}...")
        self.file_selector.clear()
        self.file_selector.setPlaceholderText("Loading...")
        self.list_files_worker = ListFilesWorker(self.manager.storage, tag_name)
        self.list_files_worker.finished_signal.connect(self.on_file_list_loaded)
        self.list_files_worker.start()

    def on_file_list_loaded(self, files, error):
        if error:
            self.status_label.setText(f"❌ List Failed: {error}")
            return
        if not files:
            self.status_label.setText("No notes found.")
        else:
            self.status_label.setText(f"Found {len(files)} notes.")
        self.file_selector.update_files(files)

    def on_file_selected(self, note_id):
        self.current_editing_note_id = note_id
        tag = self.tag_selector.get_current_tags()[0]
        
        # [核心修复] 立即更新标题，给予用户即时反馈
        current_file_name = self.file_selector.currentText()
        self.title_edit.setText(current_file_name)
        
        self.editor.setPlaceholderText("Loading content...")
        self.editor.setPlainText("")
        self.status_label.setText("Loading content...")
        
        self.load_content_worker = LoadContentWorker(self.manager.storage, note_id, tag)
        self.load_content_worker.finished_signal.connect(self.on_content_loaded)
        self.load_content_worker.start()

    def on_content_loaded(self, note, error):
        if error or not note:
            self.status_label.setText(f"❌ Load Failed: {error}")
            return
        self.status_label.setText(f"Loaded.")
        self.editor.setPlainText(note.content)
        self.editor.setReadOnly(False)
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)

    # ... (其他方法如 AI, 拖拽等保持不变，直接复制即可) ...
    def toggle_sidebar(self):
        if self.is_refined_mode:
            self.undo_refinement()
            return
        
        width_delta = self.SIDEBAR_WIDTH
        current_geo = self.geometry()
        
        if self.sidebar.isVisible():
            self.sidebar.hide()
            self.resize(current_geo.width() - width_delta, current_geo.height())
            self.ai_btn.setChecked(False) 
            self.update_ai_btn_style(False)
        else:
            self.resize(current_geo.width() + width_delta, current_geo.height())
            self.sidebar.show()
            self.sidebar.refresh_prompts()
            self.ai_btn.setChecked(True) 
            self.update_ai_btn_style(True)

    def execute_ai_task(self, prompt_template):
        current_text = self.editor.toPlainText()
        if not current_text.strip():
            self.status_label.setText("⚠️ Content is empty!")
            return
        self.raw_content = current_text
        self.current_prompt = prompt_template
        if prompt_template in self.ai_cache:
            self.on_ai_finished(True, self.ai_cache[prompt_template])
            return
        llm_instance = getattr(self.manager.source, 'llm', None)
        if not llm_instance:
             self.on_ai_finished(False, "API Key Not Found")
             return
        self.editor.setReadOnly(True)
        self.editor.setPlaceholderText("AI Processing...")
        self.status_label.setText("✨ AI is thinking...")
        self.sidebar.run_btn.setEnabled(False)
        self.sidebar.run_btn.setText("运行中...")
        QApplication.processEvents()
        self.ai_worker = AIWorker(llm_instance, prompt_template, self.raw_content)
        self.ai_worker.finished_signal.connect(self.on_ai_finished)
        self.ai_worker.start()

    def on_ai_finished(self, success, result):
        self.editor.setReadOnly(False)
        if self.sidebar.isVisible():
            self.sidebar.run_btn.setEnabled(True)
            self.sidebar.run_btn.setText("执行处理")
        if success:
            self.editor.setPlainText(result) 
            self.is_refined_mode = True
            if self.current_prompt: self.ai_cache[self.current_prompt] = result
            self.ai_btn.setText("↩ 撤销")
            self.update_ai_btn_style(True)
            self.status_label.setText("✨ Refined by AI")
            if self.sidebar.isVisible():
                self.sidebar.hide()
                geo = self.geometry()
                self.resize(geo.width() - self.SIDEBAR_WIDTH, geo.height())
        else:
            if self.editor.toPlainText() == "": self.editor.setPlainText(self.raw_content)
            self.status_label.setText(f"❌ {result}")

    def undo_refinement(self):
        self.editor.setPlainText(self.raw_content)
        self.is_refined_mode = False
        self.ai_btn.setText("✨ 润色")
        self.ai_btn.setChecked(False)
        self.update_ai_btn_style(False)
        self.status_label.setText("Restored original")

    def show_and_capture(self):
        self.sidebar.hide()
        if self.width() > 650: self.resize(600, self.height())
        self.is_refined_mode = False
        self.ai_cache = {} 
        self.current_prompt = ""
        self.ai_btn.setText("✨ 润色")
        self.ai_btn.setChecked(False)
        self.update_ai_btn_style(False)
        if self.is_append_mode:
            self.append_switch.setChecked(False)
        self.title_edit.clear()
        self.title_edit.setPlaceholderText("输入标题 (选填，留空自动生成)...")
        self.title_edit.setReadOnly(False)
        all_tags = self.manager.get_all_tags()
        self.tag_selector.refresh_tags(all_tags)
        self.status_label.setText("Processing...")
        QApplication.processEvents() 
        payload = self.manager.source.fetch()
        if payload and payload.source_text:
            self.editor.setMarkdown(payload.source_text)
            self.raw_content = payload.source_text 
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.editor.setTextCursor(cursor)
            origin = payload.origin_info.get('from', 'Unknown')
            self.status_label.setText(f"Captured from {origin}")
        else:
            self.editor.setPlainText("")
            self.raw_content = ""
            self.status_label.setText("Clipboard is empty")
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.editor.setFocus()

    def request_save(self):
        content = self.editor.toPlainText().strip()
        if not content:
            self.status_label.setText("⚠️ Content is empty!")
            return
        tags = self.tag_selector.get_current_tags()
        if not tags: tags = ["uncategorized"]
        title = self.title_edit.text().strip()
        note = Note(content=content, tags=tags, title=title, type=NoteType.TEXT)
        if self.is_append_mode and self.current_editing_note_id:
            note.id = self.current_editing_note_id
            self.update_requested_signal.emit(note)
        else:
            self.save_requested_signal.emit(note)
        self.close_window()

    def close_window(self):
        self.save_btn.setText("保存笔记")
        self.save_btn.setStyleSheet("")
        self.hide()

    def _calc_edge(self, pos: QPoint) -> int:
        edge = EDGE_NONE
        r = self.rect()
        margin = self.resize_margin
        if pos.x() < margin: edge |= EDGE_LEFT
        elif pos.x() > r.width() - margin: edge |= EDGE_RIGHT
        if pos.y() < margin: edge |= EDGE_TOP
        elif pos.y() > r.height() - margin: edge |= EDGE_BOTTOM
        return edge
    def _update_cursor(self, edge: int):
        if edge == EDGE_TOP | EDGE_LEFT or edge == EDGE_BOTTOM | EDGE_RIGHT: self.setCursor(Qt.SizeFDiagCursor)
        elif edge == EDGE_TOP | EDGE_RIGHT or edge == EDGE_BOTTOM | EDGE_LEFT: self.setCursor(Qt.SizeBDiagCursor)
        elif edge & (EDGE_LEFT | EDGE_RIGHT): self.setCursor(Qt.SizeHorCursor)
        elif edge & (EDGE_TOP | EDGE_BOTTOM): self.setCursor(Qt.SizeVerCursor)
        else: self.setCursor(Qt.ArrowCursor)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edge = self._calc_edge(event.pos())
            if edge != EDGE_NONE:
                self._resize_edge = edge
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geom = self.geometry()
            else:
                self._resize_edge = EDGE_NONE
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    def mouseMoveEvent(self, event):
        if self._resize_edge != EDGE_NONE:
            curr_pos = event.globalPosition().toPoint()
            diff = curr_pos - self._resize_start_pos
            geom = QRect(self._resize_start_geom)
            if self._resize_edge & EDGE_LEFT: geom.setLeft(geom.left() + diff.x())
            if self._resize_edge & EDGE_RIGHT: geom.setRight(geom.right() + diff.x())
            if self._resize_edge & EDGE_TOP: geom.setTop(geom.top() + diff.y())
            if self._resize_edge & EDGE_BOTTOM: geom.setBottom(geom.bottom() + diff.y())
            if geom.width() >= self.minimumWidth() and geom.height() >= self.minimumHeight():
                self.setGeometry(geom)
        elif self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        else:
            edge = self._calc_edge(event.pos())
            self._update_cursor(edge)
        event.accept()
    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_edge = EDGE_NONE
        self.setCursor(Qt.ArrowCursor)
        event.accept()
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape: self.close_window()