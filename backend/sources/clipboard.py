# backend/sources/clipboard.py

import pyperclip
from typing import Optional, Any
from backend.interfaces import SourceInterface, CapturePayload
from backend.entity import NoteType

class ClipboardSource(SourceInterface):
    """
    纯净版剪贴板数据源
    职责：只负责读取系统剪贴板，不包含任何 AI 处理逻辑
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        # 兼容旧接口签名，虽然这里不再使用 llm_client
        # 未来如果做 OCR (图片转文字)，可能在这里重新引入其他工具
        pass

    def fetch(self) -> Optional[CapturePayload]:
        try:
            # 1. 获取原生内容
            raw_content = pyperclip.paste()
            
            if raw_content is None:
                return None
            
            raw_content = str(raw_content)
            
            # 如果内容为空
            if not raw_content.strip():
                return None

            # 2. 直接封装返回，不做 AI 处理
            return CapturePayload(
                source_text=raw_content,
                source_type=NoteType.TEXT,
                raw_data=None, 
                origin_info={"from": "clipboard"}
            )

        except Exception as e:
            print(f"[ClipboardSource] Fetch Error: {e}")
            return None