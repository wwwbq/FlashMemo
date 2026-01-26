# ui/worker.py

from PySide6.QtCore import QThread, Signal
from backend.entity import Note
from backend.interfaces import StorageInterface
from backend.agent import KnowledgeAgent
from utils import LLM

class SaveWorker(QThread):
    """
    后台保存线程
    职责：接收一个 Note 和 Storage，在后台执行保存操作
    """
    # 信号：(是否成功, 提示信息)
    finished_signal = Signal(bool, str)

    def __init__(self, storage: StorageInterface, note: Note):
        super().__init__()
        self.storage = storage
        self.note = note

    def run(self):
        try:
            # 这里执行耗时的网络 IO
            success = self.storage.save(self.note)
            if success:
                self.finished_signal.emit(True, "Saved successfully")
            else:
                self.finished_signal.emit(False, "Storage returned False")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


class AIWorker(QThread):
    """
    后台 AI 处理线程
    职责：接收原始内容和 Prompt，调用 LLM，返回处理后的文本
    """
    finished_signal = Signal(bool, str)

    def __init__(self, llm: LLM, prompt_template: str, user_content: str):
        super().__init__()
        self.llm = llm
        self.prompt_template = prompt_template
        self.user_content = user_content

    def run(self):
        try:
            if not self.llm:
                self.finished_signal.emit(False, "LLM not configured")
                return

            # 简单的 Prompt 拼接策略
            # 也可以在这里做得更复杂，比如用 Jinja2 模板
            full_input = f"{self.prompt_template}\n{self.user_content}"
            
            # 清空历史，确保单次任务无状态
            self.llm.clear_history()
            
            # 调用 LLM (这是一个耗时网络操作)
            # 假设 llm.chat 返回的是字符串
            result = self.llm.chat(full_input)
            
            if result:
                self.finished_signal.emit(True, result)
            else:
                self.finished_signal.emit(False, "LLM returned empty response")
                
        except Exception as e:
            self.finished_signal.emit(False, f"AI Error: {str(e)}")


class ChatWorker(QThread):
    """
    负责调用 KnowledgeAgent 进行对话
    """
    # 信号: (回答内容, 是否出错)
    response_signal = Signal(str, bool)

    def __init__(self, agent: KnowledgeAgent, query: str, use_kb: bool):
        super().__init__()
        self.agent = agent
        self.query = query
        self.use_kb = use_kb

    def run(self):
        try:
            # 调用 agent.chat (这是一个耗时操作)
            response = self.agent.chat(self.query, use_knowledge=self.use_kb)
            self.response_signal.emit(response, False)
        except Exception as e:
            self.response_signal.emit(f"Chat Error: {str(e)}", True)


# --- [新增] 续写模式专用 Worker ---

class ListFilesWorker(QThread):
    """列出指定 Tag 下的文件列表"""
    # 信号: (文件列表 [{'id':..., 'name':...}], 错误信息)
    finished_signal = Signal(list, str)

    def __init__(self, storage: StorageInterface, tag: str):
        super().__init__()
        self.storage = storage
        self.tag = tag

    def run(self):
        try:
            files = self.storage.list_files(self.tag)
            self.finished_signal.emit(files, "")
        except Exception as e:
            self.finished_signal.emit([], str(e))

class LoadContentWorker(QThread):
    """加载指定 Note 的全文"""
    # 信号: (Note对象, 错误信息)
    finished_signal = Signal(object, str)

    def __init__(self, storage: StorageInterface, note_id: str, tag: str):
        super().__init__()
        self.storage = storage
        self.note_id = note_id
        self.tag = tag

    def run(self):
        try:
            note = self.storage.load_note_by_id(self.note_id, self.tag)
            if note:
                self.finished_signal.emit(note, "")
            else:
                self.finished_signal.emit(None, "Note not found")
        except Exception as e:
            self.finished_signal.emit(None, str(e))

class UpdateWorker(QThread):
    """更新 Note"""
    finished_signal = Signal(bool, str)

    def __init__(self, storage: StorageInterface, note: Note):
        super().__init__()
        self.storage = storage
        self.note = note

    def run(self):
        try:
            success = self.storage.update(self.note)
            if success:
                self.finished_signal.emit(True, "Updated successfully")
            else:
                self.finished_signal.emit(False, "Update failed")
        except Exception as e:
            self.finished_signal.emit(False, str(e))