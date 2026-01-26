# storage/local.py

import json
import os
import glob
import re
from typing import List, Optional, Set, Dict
from backend.entity import Note
from backend.interfaces import StorageInterface

class LocalMarkdownStorage(StorageInterface):
    def __init__(self, base_dir: str = "./data_store"):
        self.base_dir = base_dir
        self._ensure_dir_exists()

    def _ensure_dir_exists(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _sanitize_filename(self, text: str) -> str:
        text = text.replace('\n', ' ')
        clean = re.sub(r'[\\/:*?"<>|]', '_', text).strip()
        return clean[:60]

    def _get_note_path(self, tag: str, title: str) -> str:
        tag_dir = os.path.join(self.base_dir, self._sanitize_filename(tag))
        if not os.path.exists(tag_dir):
            os.makedirs(tag_dir)
        filename = f"{self._sanitize_filename(title)}.md"
        return os.path.join(tag_dir, filename)

    def _parse_markdown(self, file_path: str) -> Optional[Note]:
        """
        增强版 Markdown 解析
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 兼容性处理：去除开头的空行
            content = content.lstrip()

            if content.startswith("---"):
                # 分割 YAML 头和正文
                parts = re.split(r'^---\s*$', content, maxsplit=2, flags=re.MULTILINE)
                
                if len(parts) >= 3:
                    yaml_block = parts[1]
                    body = parts[2].strip()
                    
                    meta = {}
                    for line in yaml_block.split('\n'):
                        if ':' in line:
                            k, v = line.split(':', 1)
                            meta[k.strip()] = v.strip()
                    
                    # 还原 tags: [a, b] -> list
                    tags_str = meta.get('tags', '[]')
                    # 去掉 []，然后按逗号分割
                    tags_clean = tags_str.replace('[', '').replace(']', '')
                    tags = [t.strip() for t in tags_clean.split(',') if t.strip()]
                    
                    # 获取文件名作为备用 Title
                    file_name = os.path.basename(file_path)
                    note_title = meta.get('title', '')
                    if not note_title:
                        note_title = os.path.splitext(file_name)[0]

                    return Note(
                        id=meta.get('id', ''),
                        title=note_title,
                        created_at=meta.get('created_at', ''),
                        tags=tags,
                        content=body,
                        metadata={"filename": file_name, "origin": meta.get('origin', '')}
                    )
            return None
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None

    def _build_markdown(self, note: Note) -> str:
        tags_str = "[" + ", ".join(note.tags) + "]"
        origin = note.metadata.get('origin', '')
        
        front_matter = (
            "---\n"
            f"id: {note.id}\n"
            f"title: {note.title}\n"
            f"created_at: {note.created_at}\n"
            f"tags: {tags_str}\n"
            f"origin: {origin}\n"
            "---\n\n"
        )
        return front_matter + note.content

    def save(self, note: Note) -> bool:
        try:
            if not note.title:
                safe_time = note.created_at.split('T')[0]
                snippet = self._sanitize_filename(note.content[:10])
                note.title = f"{safe_time}_{snippet}"

            md_content = self._build_markdown(note)
            target_tags = note.tags if note.tags else ["Uncategorized"]

            for tag in target_tags:
                path = self._get_note_path(tag, note.title)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(md_content)
            return True
        except Exception as e:
            print(f"[Local] Save Error: {e}")
            return False

    def load(self, tag: Optional[str] = None) -> List[Note]:
        notes = []
        search_path = os.path.join(self.base_dir, "**", "*.md")
        if tag:
            search_path = os.path.join(self.base_dir, self._sanitize_filename(tag), "*.md")

        files = glob.glob(search_path, recursive=True)
        seen_ids = set()

        for path in files:
            note = self._parse_markdown(path)
            if note and note.id not in seen_ids:
                # [修复] 只有当 note 自身没有解析出 tags 时，才用传入的 tag 补全
                # 这样可以保留原始的多标签信息
                if not note.tags and tag:
                    note.tags = [tag]
                
                notes.append(note)
                seen_ids.add(note.id)
        
        notes.sort(key=lambda x: x.created_at, reverse=True)
        return notes

    def get_all_tags(self) -> List[str]:
        if not os.path.exists(self.base_dir): return []
        # 扫描目录
        return sorted([d for d in os.listdir(self.base_dir) if os.path.isdir(os.path.join(self.base_dir, d))])

    def list_files(self, tag: str) -> List[Dict[str, str]]:
        tag_dir = os.path.join(self.base_dir, self._sanitize_filename(tag))
        if not os.path.exists(tag_dir): return []

        results = []
        files = glob.glob(os.path.join(tag_dir, "*.md"))
        files.sort(key=os.path.getmtime, reverse=True)

        for path in files:
            # 这里为了速度，还是得解析一下ID，不然无法对应
            note = self._parse_markdown(path)
            if note:
                results.append({'id': note.id, 'name': note.title})
        return results

    def load_note_by_id(self, note_id: str, tag: str) -> Optional[Note]:
        tag_dir = os.path.join(self.base_dir, self._sanitize_filename(tag))
        if not os.path.exists(tag_dir): return None

        files = glob.glob(os.path.join(tag_dir, "*.md"))
        for path in files:
            note = self._parse_markdown(path)
            if note and note.id == note_id:
                return note
        return None

    def update(self, note: Note) -> bool:
        """
        覆盖更新：全量扫描 ID，删除旧文件，保存新文件
        """
        deleted_count = 0
        all_files = glob.glob(os.path.join(self.base_dir, "**", "*.md"), recursive=True)
        
        for path in all_files:
            n = self._parse_markdown(path)
            # 只要 ID 匹配，就视为同一个笔记的旧版本（可能是不同Tag下的副本，或者是旧Title）
            if n and n.id == note.id:
                try:
                    os.remove(path)
                    deleted_count += 1
                    print(f"🗑️ Deleted old file: {path}")
                except Exception as e:
                    print(f"⚠️ Failed to delete {path}: {e}")
        
        if deleted_count == 0:
            print("⚠️ Update warning: No old files found to delete (creating new one).")

        return self.save(note)