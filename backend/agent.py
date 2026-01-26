# backend/agent.py

from abc import ABC, abstractmethod
from typing import List
from backend.entity import Note
from backend.interfaces import StorageInterface
from backend.prompt_loader import PromptLoader
from utils import LLM

class RetrieverInterface(ABC):
    @abstractmethod
    def retrieve(self, query: str, router_prompt_template: str, limit: int = 10) -> List[Note]:
        pass

class TagRouteRetriever(RetrieverInterface):
    def __init__(self, storage: StorageInterface, llm: LLM):
        self.storage = storage
        self.llm = llm

    def retrieve(self, query: str, router_prompt_template: str, limit: int = 20) -> List[Note]:
        if not self.llm: return []
        all_tags = self.storage.get_all_tags()
        if not all_tags: return []

        selected_tags = self._ask_llm_to_pick_tags(query, all_tags, router_prompt_template)
        if selected_tags: print(f"🤖 [Agent] Router selected: {selected_tags}")

        candidates = []
        seen_ids = set()
        for tag in selected_tags:
            tag_notes = self.storage.load(tag)
            for note in tag_notes:
                if note.id not in seen_ids:
                    candidates.append(note)
                    seen_ids.add(note.id)
        candidates.sort(key=lambda x: x.created_at, reverse=True)
        return candidates[:limit]

    def _ask_llm_to_pick_tags(self, query: str, all_tags: List[str], template: str) -> List[str]:
        tags_str = ", ".join(all_tags)
        prompt = template.replace("{all_tags}", f"[{tags_str}]").replace("{query}", query)
        response = self.llm.chat(prompt, use_history=False)
        if not response or "None" in response: return []
        picked = [t.strip() for t in response.split(',')]
        valid_tags = [t for t in picked if t in all_tags]
        return valid_tags

class KnowledgeAgent:
    def __init__(self, storage: StorageInterface, llm: LLM, prompts_dir: str):
        self.storage = storage
        self.llm = llm
        self.loader = PromptLoader(prompts_dir)
        self.retriever: RetrieverInterface = TagRouteRetriever(storage, llm)

    def _load_prompt(self, name: str, default: str) -> str:
        prompts = self.loader.load_prompts()
        return prompts.get(name, default)

    def clear_history(self):
        if self.llm: self.llm.clear_history()

    def chat(self, user_input: str, use_knowledge: bool = False) -> str:
        if not self.llm: return "❌ AI 模块未配置。"

        if not use_knowledge:
            print("💬 [Agent] Normal Chat Mode")
            return self.llm.chat(user_input, use_history=True)

        print("🔌 [Agent] Knowledge Base Mode")
        router_template = self._load_prompt("rag_router", "{query} {all_tags}")
        summary_template = self._load_prompt("rag_summary", "{context} {query}")

        relevant_notes = self.retriever.retrieve(user_input, router_template)
        
        context_str = ""
        if relevant_notes:
            for i, note in enumerate(relevant_notes):
                clean_content = note.content.replace('\n', ' ')[:500]
                
                # [修改] 使用 filename (真实或虚拟)
                file_name = note.metadata.get('filename', 'Unknown_File')
                
                # 提示 LLM：这是资料的来源信息，请在回答中引用
                meta_info = f"标签: {note.tags}, 文件名: {file_name}"
                context_str += f"> [资料{i+1}] ({meta_info})\n内容: {clean_content}\n\n"
        else:
            context_str = "（本次检索未发现匹配的笔记）"

        final_prompt = summary_template.replace("{context}", context_str).replace("{query}", user_input)
        return self.llm.chat(final_prompt, use_history=True)