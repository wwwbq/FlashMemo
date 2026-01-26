# ui/styles.py

# 颜色定义
COLORS = {
    "background": "#202124",       # 深灰背景
    "input_bg": "#303134",         # 输入框背景
    "text": "#E8EAED",             # 主要文字颜色
    "placeholder": "#9AA0A6",      # 提示文字颜色
    "accent": "#8AB4F8",           # 强调色 (蓝色)
    "success": "#81C995",          # 成功色 (绿色)
    "border": "#5F6368",           # 边框色
    "toggle_off": "#494C50",       
    "toggle_on": "#1E8E3E"         
}

FONT_FAMILY = '".AppleSystemUIFont", "Microsoft YaHei", "Segoe UI", sans-serif'

# 全局样式表
MAIN_STYLES = f"""
    QWidget {{
        background-color: {COLORS['background']};
        color: {COLORS['text']};
        font-family: {FONT_FAMILY};
        font-size: 14px;
    }}

    /* 文本编辑器 */
    QTextEdit {{
        background-color: {COLORS['input_bg']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        padding: 12px;
        selection-background-color: {COLORS['accent']};
    }}

    /* ---------------------------------------------------- */
    /* 统一 ComboBox 和 LineEdit */
    /* ---------------------------------------------------- */
    QComboBox {{
        background-color: {COLORS['input_bg']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 6px 12px;
        color: {COLORS['text']};
        font-size: 14px;
        height: 20px;
    }}
    QComboBox::drop-down {{ border: 0px; width: 24px; }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid {COLORS['placeholder']};
        margin-right: 5px;
    }}
    QComboBox QAbstractItemView {{
        background-color: #2D2E30;
        border: 1px solid {COLORS['border']};
        selection-background-color: #494C50;
        selection-color: {COLORS['text']};
        outline: none;
        padding: 4px;
        font-size: 14px;
    }}
    
    QLineEdit {{
        background-color: {COLORS['input_bg']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 6px 12px;
        color: {COLORS['text']};
        font-size: 14px;
        height: 20px;
    }}
    QLineEdit:focus {{ border: 1px solid {COLORS['accent']}; }}
    QToolTip {{
        background-color: {COLORS['input_bg']};
        color: {COLORS['text']};
        border: 1px solid {COLORS['border']};
        padding: 4px;
    }}

    /* ---------------------------------------------------- */
    /* 按钮与开关 */
    /* ---------------------------------------------------- */

    QPushButton#SaveBtn {{
        background-color: {COLORS['accent']};
        color: #202124;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: bold;
    }}
    QPushButton#SaveBtn:hover {{ background-color: #AECBFA; }}
    QPushButton#SaveBtn:pressed {{ background-color: #669DF6; }}

    /* [修改] 知识库 CheckBox 样式优化 */
    QCheckBox#KBCheckBox {{
        color: {COLORS['placeholder']};
        font-weight: bold;
        spacing: 8px;
    }}
    QCheckBox#KBCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid {COLORS['border']};
        background: transparent;
    }}
    QCheckBox#KBCheckBox::indicator:checked {{
        background-color: {COLORS['success']};
        border: 1px solid {COLORS['success']};
        image: url(none); /* 简单用颜色区分 */
    }}
    QCheckBox#KBCheckBox:checked {{
        color: {COLORS['success']}; /* 文字变绿 */
    }}
"""