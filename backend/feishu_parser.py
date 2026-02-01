# backend/feishu_parser.py

import mistletoe
from mistletoe.base_renderer import BaseRenderer
from mistletoe.block_token import Heading, Quote, CodeFence, List, ListItem, Paragraph
from mistletoe.span_token import RawText, Strong, Emphasis, Link, InlineCode

class FeishuRenderer(BaseRenderer):
    """
    将 Markdown AST 渲染为飞书 Block 结构
    """
    def __init__(self):
        super().__init__()
        self.blocks = []

    def render(self, token):
        # 入口方法：返回 block 列表
        self.blocks = []
        self.render_inner(token)
        return self.blocks

    def render_inner(self, token):
        # 递归遍历 AST
        if hasattr(token, 'children'):
            for child in token.children:
                self.render_token(child)

    def render_token(self, token):
        # 根据 token 类型分发
        cls_name = type(token).__name__
        handler = getattr(self, f'render_{cls_name}', self.render_fallback)
        handler(token)

    # --- Block Handlers ---

    def render_Document(self, token):
        self.render_inner(token)

    def render_Heading(self, token):
        level = token.level
        # 飞书 heading 支持 1-9，block_type=3对应H1，4对应H2...
        block_type = 2 + level 
        text_elements = self._extract_inline_elements(token)
        
        self.blocks.append({
            "block_type": block_type,
            f"heading{level}": {
                "elements": text_elements
            }
        })

    def render_Paragraph(self, token):
        text_elements = self._extract_inline_elements(token)
        self.blocks.append({
            "block_type": 2, # Text
            "text": {
                "elements": text_elements
            }
        })

    def render_CodeFence(self, token):
        content = token.children[0].content
        self.blocks.append({
            "block_type": 14, # Code
            "code": {
                "language": 1, # Plain Text (或者根据 token.language 映射)
                "elements": [{"text_run": {"content": content}}]
            }
        })

    def render_List(self, token):
        # 列表比较复杂，飞书要求每项是一个 block
        # 这里简化处理：递归渲染 ListItem
        self.render_inner(token)

    def render_ListItem(self, token):
        # 获取列表项内容
        # 飞书 Bullet List block_type=12, Ordered=13
        # mistletoe 的 ListItem 不太好区分有序无序，这里统一用无序
        # 如果要精确，需要从父级 List token 判断
        
        # 简单提取文本
        elements = []
        # ListItem 的 children 通常是 Paragraph，我们只需要 Paragraph 里的内容
        if token.children and isinstance(token.children[0], Paragraph):
             elements = self._extract_inline_elements(token.children[0])
        
        self.blocks.append({
            "block_type": 12, # Bullet
            "bullet": {
                "elements": elements
            }
        })

    def render_Quote(self, token):
        # 引用 -> Callout
        # 提取引用内部的文本
        text_content = ""
        # 简化：只取纯文本
        if token.children and hasattr(token.children[0], 'children'):
             # 这里逻辑比较深，简化处理
             pass
             
        self.blocks.append({
            "block_type": 19,
            "callout": {
                "background_color": 5,
                "element": {
                    "elements": [{"text_run": {"content": "引用内容 (复杂结构暂略)"}}]
                }
            }
        })

    def render_fallback(self, token):
        # 未知块，忽略或转为纯文本
        pass

    # --- Helper: 提取行内样式 (Span Tokens) ---
    
    def _extract_inline_elements(self, token):
        """
        将 Paragraph/Heading 内部的 Span Token 转换为飞书的 TextElement 列表
        支持 粗体、斜体、链接
        """
        elements = []
        
        if not hasattr(token, 'children'):
            return elements

        for child in token.children:
            style = {}
            content = ""
            
            if isinstance(child, RawText):
                content = child.content
            elif isinstance(child, Strong): # **Bold**
                content = child.children[0].content
                style["bold"] = True
            elif isinstance(child, Emphasis): # *Italic*
                content = child.children[0].content
                style["italic"] = True
            elif isinstance(child, InlineCode): # `code`
                content = child.children[0].content
                style["code_inline"] = True # 飞书 API 可能不支持 code_inline 样式，视版本而定
            elif isinstance(child, Link):
                content = child.children[0].content if hasattr(child.children[0], 'content') else "Link"
                # Link 需要特殊的 text_link 结构，这里简化为纯文本带样式
                style["underline"] = True
            
            if content:
                element = {"text_run": {"content": content}}
                if style:
                    element["text_run"]["text_style"] = style
                elements.append(element)
                
        return elements

def parse_markdown_to_feishu(markdown_text: str) -> list:
    """对外接口"""
    with FeishuRenderer() as renderer:
        return renderer.render(mistletoe.Document(markdown_text))