# backend/models.py

import uuid
import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Optional, Any

class NoteType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    MIXED = "mixed"

@dataclass
class Attachment:
    type: str
    path: str
    filename: str
    meta: Dict = field(default_factory=dict)

@dataclass
class Note:
    """
    笔记实体类
    """
    content: str
    tags: List[str]
    
    # [新增] 标题字段
    title: str = "" 
    
    type: NoteType = NoteType.TEXT
    attachments: List[Attachment] = field(default_factory=list)

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    
    # metadata 用于存储不需要直接展示但很重要的信息 (如原始文件名、来源URL等)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        note_type = data.get("type", NoteType.TEXT)
        try:
            note_type = NoteType(note_type)
        except ValueError:
            note_type = NoteType.TEXT

        attachments_data = data.get("attachments", [])
        attachments = [Attachment(**item) for item in attachments_data]

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""), # 读取标题
            content=data.get("content", ""),
            tags=data.get("tags", []),
            type=note_type,
            attachments=attachments,
            created_at=data.get("created_at", datetime.datetime.now().isoformat()),
            metadata=data.get("metadata", {})
        )