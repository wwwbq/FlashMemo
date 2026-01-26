from typing import List
from backend.entity import Note
from backend.interfaces import SourceInterface, StorageInterface

class NoteManager:
    """
    核心业务控制器
    Source -> Note -> Storage
    """

    def __init__(self, source: SourceInterface, storage: StorageInterface):
        self.source = source
        self.storage = storage

    def execute_capture_workflow(self, tags: List[str]) -> tuple[bool, str]:
        # 1. 获取 Payload 对象
        payload = self.source.fetch()
        
        if not payload: # 这里 payload 可能是 None
            return False, "Source content is empty"

        # 2. Object Mapping: Payload -> Note Entity
        # 如果未来 Payload 包含图片，我们可以在这里处理附件保存逻辑
        
        note = Note(
            content=payload.source_text, # 核心文本
            tags=tags,
            type=payload.source_type,    # 记录类型
            # 如果 payload.raw_data 有东西，可以在这里处理并存入 attachments
            attachments=[], 
            metadata=payload.origin_info
        )

        # 3. Save
        success = self.storage.save(note)
        
        if success:
            return True, f"Saved to {tags}"
        else:
            return False, "Storage failed"

    def get_all_tags(self) -> List[str]:
        return self.storage.get_all_tags()