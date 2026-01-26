# backend/interfaces.py

from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from dataclasses import dataclass, field
from backend.entity import Note, NoteType

@dataclass
class CapturePayload:
    source_text: str = ""
    source_type: NoteType = NoteType.TEXT
    raw_data: Any = None
    origin_info: dict = field(default_factory=dict)

class SourceInterface(ABC):
    @abstractmethod
    def fetch(self) -> Optional[CapturePayload]:
        pass

class StorageInterface(ABC):
    @abstractmethod
    def save(self, note: Note) -> bool:
        pass
    
    @abstractmethod
    def load(self, tag: Optional[str] = None) -> List[Note]:
        """批量加载笔记 (用于 RAG)"""
        pass

    @abstractmethod
    def get_all_tags(self) -> List[str]:
        pass

    # --- [新增] 续写模式专用接口 ---

    @abstractmethod
    def list_files(self, tag: str) -> List[Dict[str, str]]:
        """
        列出指定 Tag 下的所有文件摘要
        :param tag: 标签名
        :return: [{'id': '文件ID', 'name': '完整文件名'}, ...]
        """
        pass

    @abstractmethod
    def load_note_by_id(self, note_id: str, tag: str) -> Optional[Note]:
        """
        根据 ID (和 Tag) 读取单条笔记全文
        :param note_id: 文件的唯一标识 (Local用uuid, Feishu用token)
        :param tag: 文件所属标签 (用于定位本地文件)
        """
        pass

    @abstractmethod
    def update(self, note: Note) -> bool:
        """
        覆盖更新一条笔记
        """
        pass