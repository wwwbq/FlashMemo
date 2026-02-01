# storage/remote_feishu.py

import requests
import time
import concurrent.futures 
import re 
import json
from typing import List, Optional, Dict
from backend.interfaces import StorageInterface
from backend.entity import Note
from backend.feishu_parser import parse_markdown_to_feishu

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
        else:
            print(f"❌ [Feishu] Auth Failed: {data}")
            return ""

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json; charset=utf-8"
        }

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

    def _delete_file(self, file_token: str) -> bool:
        url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}"
        params = {"type": "docx"} 
        try:
            requests.delete(url, params=params, headers=self.headers)
            return True
        except: return False

    # --- 写入逻辑 ---
    def _write_blocks(self, doc_id: str, note: Note) -> bool:
        children = []
        # Meta Block
        meta_dict = {
            "id": note.id,
            "tags": note.tags,
            "created_at": note.created_at,
            "origin": note.metadata.get('origin', '')
        }
        meta_json = json.dumps(meta_dict, ensure_ascii=False)
        children.append({
            "block_type": 14,
            "code": {"language": 25, "wrap": True, "elements": [{"text_run": {"content": meta_json}}]}
        })

        # Source
        origin = note.metadata.get('origin') or note.metadata.get('from')
        if origin:
            children.append({
                "block_type": 19, 
                "callout": {"background_color": 5, "element": {"elements": [{"text_run": {"content": f"Source: {origin}"}}]}}
            })

        # [关键] 调用后端 Markdown Parser
        try:
            content_blocks = parse_markdown_to_feishu(note.content)
            children.extend(content_blocks)
        except Exception as e:
            print(f"MD Parse Error: {e}")
            children.append({
                "block_type": 2, 
                "text": {"elements": [{"text_run": {"content": note.content}}]}
            })

        # Tags
        tag_str = " ".join([f"#{t}" for t in note.tags])
        children.append({
            "block_type": 2, 
            "text": {"elements": [{"text_run": {"content": f"\nTags: {tag_str}", "text_style": {"italic": True, "color": {"token": "grey"}}}}]}
        })

        write_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
        resp = requests.post(write_url, json={"children": children}, headers=self.headers)
        return resp.json().get("code") == 0

    # --- 保存 ---
    def save(self, note: Note) -> bool:
        target_tags = note.tags if note.tags else ["Uncategorized"]
        
        if not note.title:
            safe_time = note.created_at.split('T')[0]
            snippet = self._sanitize_filename(note.content[:10])
            note.title = f"{safe_time}_{snippet}"

        success_count = 0
        for tag in target_tags:
            folder_token = self._get_or_create_tag_folder(tag)
            if not folder_token: continue

            create_url = "https://open.feishu.cn/open-apis/docx/v1/documents"
            resp = requests.post(create_url, json={"folder_token": folder_token, "title": note.title}, headers=self.headers)
            if resp.json().get("code") != 0: continue
            
            doc_id = resp.json()["data"]["document"]["document_id"]
            if self._write_blocks(doc_id, note):
                success_count += 1

        return success_count > 0

    # --- 更新 ---
    def update(self, note: Note) -> bool:
        self._delete_file(note.id)
        return self.save(note)

    # --- 加载列表 ---
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

    # --- 读取单篇内容 (Markdown 还原) ---
    def load_note_by_id(self, note_id: str, tag: str) -> Optional[Note]:
        return self._fetch_doc_content(note_id, doc_name="Loading...") 

    def _fetch_doc_content(self, doc_token: str, doc_name: str) -> Optional[Note]:
        try:
            url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks"
            resp = requests.get(url, headers=self.headers)
            if resp.json().get("code") != 0: return None
            
            blocks = resp.json()["data"]["items"]
            content_parts = []
            
            for block in blocks:
                b_type = block["block_type"]
                text_content = ""
                
                # 提取文本内容
                if b_type == 2: # Text
                    text_content = self._extract_text_from_elements(block.get("text", {}).get("elements", []))
                
                elif b_type >= 3 and b_type <= 11: # Headings (3=H1, 4=H2...)
                    level = b_type - 2
                    raw_text = self._extract_text_from_elements(block.get(f"heading{level}", {}).get("elements", []))
                    if raw_text:
                        text_content = f"{'#' * level} {raw_text}" # 还原标题符号
                
                elif b_type == 12: # Bullet List
                    raw_text = self._extract_text_from_elements(block.get("bullet", {}).get("elements", []))
                    if raw_text:
                        text_content = f"- {raw_text}" # 还原列表符号
                
                elif b_type == 13: # Ordered List
                    raw_text = self._extract_text_from_elements(block.get("ordered", {}).get("elements", []))
                    if raw_text:
                        text_content = f"1. {raw_text}" # 简化还原
                
                elif b_type == 14: # Code Block
                    code_text = self._extract_text_from_elements(block.get("code", {}).get("elements", []))
                    # 跳过我们自己的 Meta Block (JSON)
                    if code_text.strip().startswith("{") and '"id":' in code_text:
                        continue 
                    text_content = f"```\n{code_text}\n```" # 还原代码块符号

                elif b_type == 19: # Callout (Source)
                    # 忽略 Source Callout
                    continue

                if text_content:
                    # 过滤底部的 Tags 元数据
                    if text_content.strip().startswith("Tags:"): continue
                    content_parts.append(text_content)
            
            full_text = "\n\n".join(content_parts).strip()
            
            return Note(
                id=doc_token,
                content=full_text,
                tags=[], 
                metadata={"title": doc_name, "filename": doc_name}
            )
        except Exception as e:
            print(f"Error parsing doc: {e}")
            return None

    def _extract_text_from_elements(self, elements: list) -> str:
        """从 TextRun 中提取纯文本"""
        res = []
        for elem in elements:
            if "text_run" in elem:
                res.append(elem["text_run"]["content"])
        return "".join(res)

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
                    if not note.tags: note.tags = [tag]
                    notes.append(note)
        return notes

    def get_all_tags(self) -> List[str]:
        self._folder_cache = {}
        list_url = f"https://open.feishu.cn/open-apis/drive/v1/files?folder_token={self.root_token}"
        resp = requests.get(list_url, headers=self.headers)
        tags = []
        if resp.status_code == 200 and resp.json().get("code") == 0:
            files = resp.json().get("data", {}).get("files", [])
            for f in files:
                if f["type"] == "folder":
                    self._folder_cache[f["name"]] = f["token"]
                    tags.append(f["name"])
        return sorted(tags)