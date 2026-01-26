# ui/sidebar.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTextEdit, 
                               QComboBox, QPushButton)
from PySide6.QtCore import Qt, Signal
from backend.prompt_loader import PromptLoader
from ui.styles import COLORS

class AISidebar(QWidget):
    """
    AI 侧边栏组件
    """
    run_ai_signal = Signal(str)

    def __init__(self, prompts_dir: str, parent=None):
        super().__init__(parent)
        
        # [修改] 接收外部传入的路径
        self.prompts_dir = prompts_dir
        self.loader = PromptLoader(prompts_dir=self.prompts_dir)
        self.current_prompts_map = {} 
        
        self.setup_ui()
        self.refresh_prompts() 

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(15)

        title = QLabel("✨ AI 助手")
        title.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 16px;")
        layout.addWidget(title)

        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setPlaceholderText("Prompt preview...")
        self.preview_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['background']}; 
                border: 1px dashed {COLORS['border']};
                color: {COLORS['placeholder']};
                font-size: 12px;
            }}
        """)
        layout.addWidget(self.preview_edit, stretch=1)

        layout.addWidget(QLabel("选择指令:", styleSheet=f"color:{COLORS['text']}"))
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self.on_prompt_changed)
        layout.addWidget(self.combo)

        self.run_btn = QPushButton("执行处理")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['input_bg']};
                border: 1px solid {COLORS['accent']};
                color: {COLORS['accent']};
                padding: 8px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent']};
                color: {COLORS['background']};
            }}
        """)
        self.run_btn.clicked.connect(self.on_run_clicked)
        layout.addWidget(self.run_btn)

        self.setFixedWidth(320)
        self.setStyleSheet(f"""
            AISidebar {{
                background-color: #2D2E30;
                border-left: 1px solid {COLORS['border']};
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }}
        """)

    def refresh_prompts(self):
        self.current_prompts_map = self.loader.load_prompts()
        self.combo.clear()
        
        if self.current_prompts_map:
            names = list(self.current_prompts_map.keys())
            self.combo.addItems(names)
            self.combo.setCurrentIndex(0)
            self.on_prompt_changed(0)
            self.run_btn.setEnabled(True)
        else:
            self.preview_edit.setText(f"未找到 Prompt 文件。\n请检查目录:\n{self.prompts_dir}")
            self.run_btn.setEnabled(False)

    def on_prompt_changed(self, index):
        name = self.combo.currentText()
        content = self.current_prompts_map.get(name, "")
        self.preview_edit.setPlainText(content)

    def on_run_clicked(self):
        prompt_content = self.preview_edit.toPlainText()
        if prompt_content:
            self.run_ai_signal.emit(prompt_content)