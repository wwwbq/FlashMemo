# storage/remote_feishu.py

import requests
import time
import concurrent.futures 
import json
import re
from typing import List, Optional, Dict
from backend.interfaces import StorageInterface
from backend.entity import Note

class FeishuDocStorage(StorageInterface):
    def __init__(self, app_id: str, app_secret: str, root_token: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.root_token = root_token
        
        self._token = ""
        self._token_expires_at = 0
        self._folder_cache: Dict[str, str] = {} 

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at - 300:
            return self._token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret})
        data = resp.json()
        if data.get("code") == 0:
            self._token = data["tenant_access_token"]
            self._token_expires_at = now + data["expire"]
            return self._token
        return ""

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json; charset=utf-8"}

    def _get_or_create_tag_folder(self, tag_name: str) -> Optional[str]:
        if tag_name in self._folder_cache: return self._folder_cache[tag_name]
        self.get_all_tags() 
        if tag_name in self._folder_cache: return self._folder_cache[tag_name]

        create_url = "https://open.feishu.cn/open-apis/drive/v1/files/create_folder"
        payload = {"name": tag_name, "folder_token": self.root_token}
        resp = requests.post(create_url, json=payload, headers=self.headers)
        if resp.json().get("code") == 0:
            new_token = resp.json()["data"]["token"]
            self._folder_cache[tag_name] = new_token
            return new_token
        return None

    def _sanitize_filename(self, text: str) -> str:
        text = text.replace('\n', ' ')
        return re.sub(r'[\\/:*?"<>|]', '_', text).strip()[:50]

    # --- 核心：构造文档内容 (Meta Block + Content) ---

    def _write_blocks(self, doc_id: str, note: Note) -> bool:
        children = []
        
        # [新增] 1. Metadata Code Block (JSON格式)
        meta_dict = {
            "id": note.id,
            "tags": note.tags,
            "created_at": note.created_at,
            "origin": note.metadata.get('origin', '')
        }
        meta_json = json.dumps(meta_dict, ensure_ascii=False)
        
        children.append({
            "block_type": 14, # Code Block
            "code": {
                "language": 25, # JSON
                "wrap": True,
                "elements": [{"text_run": {"content": meta_json}}]
            }
        })

        # 2. 正文
        children.append({
            "block_type": 2, 
            "text": {"elements": [{"text_run": {"content": note.content}}]}
        })

        write_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
        resp = requests.post(write_url, json={"children": children}, headers=self.headers)
        return resp.json().get("code") == 0

    def _delete_file(self, file_token: str) -> bool:
        url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}"
        try:
            requests.delete(url, params={"type": "docx"}, headers=self.headers)
            return True
        except: return False

    # --- 接口实现 ---

    def save(self, note: Note) -> bool:
        target_tags = note.tags if note.tags else ["Uncategorized"]
        
        # 自动标题兜底
        if not note.title:
            safe_time = note.created_at.split('T')[0]
            snippet = self._sanitize_filename(note.content[:10])
            note.title = f"{safe_time}_{snippet}"

        success_count = 0
        for tag in target_tags:
            folder_token = self._get_or_create_tag_folder(tag)
            if not folder_token: continue

            # 创建文档 (使用 title)
            create_url = "https://open.feishu.cn/open-apis/docx/v1/documents"
            resp = requests.post(create_url, json={"folder_token": folder_token, "title": note.title}, headers=self.headers)
            if resp.json().get("code") != 0: continue
            
            doc_id = resp.json()["data"]["document"]["document_id"]
            if self._write_blocks(doc_id, note):
                success_count += 1

        return success_count > 0

    def load(self, tag: Optional[str] = None) -> List[Note]:
        if not tag: return []
        folder_token = self._get_or_create_tag_folder(tag)
        if not folder_token: return []

        list_url = f"https://open.feishu.cn/open-apis/drive/v1/files?folder_token={folder_token}"
        resp = requests.get(list_url, headers=self.headers)
        if resp.json().get("code") != 0: return []
            
        files = resp.json().get("data", {}).get("files", [])
        docs = [f for f in files if f["type"] == "docx"]
        
        notes = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_doc = {
                executor.submit(self._fetch_doc_content, d["token"], d["name"]): d 
                for d in docs
            }
            for future in concurrent.futures.as_completed(future_to_doc):
                note = future.result()
                if note:
                    # [修复] 不要覆盖 tags，只有当 note 自身没解析出 tags 时才补全
                    if not note.tags:
                        note.tags = [tag]
                    notes.append(note)
        return notes

    def _fetch_doc_content(self, doc_token: str, doc_name: str) -> Optional[Note]:
        try:
            url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks"
            resp = requests.get(url, headers=self.headers)
            if resp.json().get("code") != 0: return None
            
            blocks = resp.json()["data"]["items"]
            content_parts = []
            meta_data = {}
            
            # 解析第一个块是否为 Meta CodeBlock
            first_block = blocks[0] if blocks else None
            is_meta_block = False
            
            if first_block and first_block["block_type"] == 14: # Code
                try:
                    code_text = first_block["code"]["elements"][0]["text_run"]["content"]
                    # 尝试解析 JSON
                    meta_data = json.loads(code_text)
                    if "id" in meta_data: # 确认是我们的 Meta
                        is_meta_block = True
                except: pass

            # 遍历剩余块提取正文
            start_index = 1 if is_meta_block else 0
            
            for block in blocks[start_index:]:
                b_type = block["block_type"]
                text_elem = None
                if b_type == 2: text_elem = block.get("text")
                elif 3 <= b_type <= 9: text_elem = block.get(f"heading{b_type - 2}")
                
                if text_elem and "elements" in text_elem:
                    for elem in text_elem["elements"]:
                        if "text_run" in elem:
                            content_parts.append(elem["text_run"]["content"])
            
            full_text = "\n".join(content_parts).strip()
            
            # 还原 Note
            return Note(
                id=meta_data.get("id", doc_token), # 优先用 Meta 里的 ID
                title=doc_name,
                content=full_text,
                tags=meta_data.get("tags", []),
                created_at=meta_data.get("created_at", ""),
                metadata={"title": doc_name, "filename": doc_name}
            )
        except: return None

    def list_files(self, tag: str) -> List[Dict[str, str]]:
        folder_token = self._get_or_create_tag_folder(tag)
        if not folder_token: return []
        resp = requests.get(f"https://open.feishu.cn/open-apis/drive/v1/files?folder_token={folder_token}", headers=self.headers)
        results = []
        if resp.json().get("code") == 0:
            files = resp.json().get("data", {}).get("files", [])
            for f in files:
                if f["type"] == "docx":
                    results.append({'id': f["token"], 'name': f["name"]})
        return results

    def load_note_by_id(self, note_id: str, tag: str) -> Optional[Note]:
        return self._fetch_doc_content(note_id, doc_name="Loading...") 

    def update(self, note: Note) -> bool:
        """更新：先删除旧文件，再保存新文件"""
        # 对于飞书，note.id 可能是旧文档的 token，或者是 meta 里的 uuid
        # 这里有一个潜在问题：如果 note.id 是 uuid，我们没法直接删文件（需要 token）
        # 所以 update 传进来的 note，其 id 必须是 doc_token
        
        # 这里简化处理：直接删掉传入的 id 对应的文件
        self._delete_file(note.id)
        return self.save(note)
    
    def get_all_tags(self) -> List[str]:
        self._folder_cache = {}
        resp = requests.get(f"https://open.feishu.cn/open-apis/drive/v1/files?folder_token={self.root_token}", headers=self.headers)
        tags = []
        if resp.json().get("code") == 0:
            for f in resp.json().get("data", {}).get("files", []):
                if f["type"] == "folder":
                    self._folder_cache[f["name"]] = f["token"]
                    tags.append(f["name"])
        return sorted(tags)