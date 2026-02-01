# ui/highlighter.py

from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression, Qt
from ui.styles import COLORS

class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # --- 1. 标题 (# Header) ---
        header_format = QTextCharFormat()
        header_format.setForeground(QColor(COLORS['accent'])) # 蓝色
        header_format.setFontWeight(QFont.Bold)
        # 匹配以 # 开头的行
        self.rules.append((QRegularExpression(r"^#+ .*"), header_format))

        # --- 2. 粗体 (**Bold**) ---
        bold_format = QTextCharFormat()
        bold_format.setFontWeight(QFont.Bold)
        bold_format.setForeground(QColor("#E8EAED")) # 亮白
        self.rules.append((QRegularExpression(r"\*\*.*?\*\*"), bold_format))

        # --- 3. 代码块 (``` ... ```) ---
        code_format = QTextCharFormat()
        code_format.setForeground(QColor("#AECBFA")) # 浅蓝
        code_format.setFontFamily("Consolas") # 等宽字体
        self.rules.append((QRegularExpression(r"```[\s\S]*?```"), code_format))
        
        # --- 4. 行内代码 (`code`) ---
        inline_code_format = QTextCharFormat()
        inline_code_format.setForeground(QColor("#AECBFA"))
        self.rules.append((QRegularExpression(r"`[^`]+`"), inline_code_format))

        # --- 5. 列表 (- item) ---
        list_format = QTextCharFormat()
        list_format.setForeground(QColor(COLORS['success'])) # 绿色
        self.rules.append((QRegularExpression(r"^\s*[\-\*] .*"), list_format))

        # --- 6. 引用 (> quote) ---
        quote_format = QTextCharFormat()
        quote_format.setForeground(QColor(COLORS['placeholder'])) # 灰色
        quote_format.setFontItalic(True)
        self.rules.append((QRegularExpression(r"^> .*"), quote_format))

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)