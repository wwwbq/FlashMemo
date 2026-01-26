# backend/prompt_loader.py

import os
from typing import Dict, List

class PromptLoader:
    """
    Prompt 文件加载器
    职责：读取指定目录下的 .txt 文件，构建 Prompt 字典
    """
    def __init__(self, prompts_dir: str = "./prompts"):
        self.prompts_dir = prompts_dir
        self._ensure_dir_exists()

    def _ensure_dir_exists(self):
        """如果目录不存在，创建一个"""
        if not os.path.exists(self.prompts_dir):
            try:
                os.makedirs(self.prompts_dir)
                # 创建一个默认的 demo prompt
                self._create_default_prompt()
            except Exception as e:
                print(f"❌ Error creating prompts dir: {e}")

    def _create_default_prompt(self):
        """生成一个默认的润色 Prompt"""
        default_path = os.path.join(self.prompts_dir, "默认润色.txt")
        content = (
            "你是一个专业的文本编辑助手。\n"
            "请对以下内容进行格式清洗、去除乱码、修正标点和换行，使其阅读通顺。\n"
            "请直接输出润色后的结果，不要包含任何解释性语言。"
        )
        with open(default_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def load_prompts(self) -> Dict[str, str]:
        """
        加载所有 Prompt
        :return: { "文件名": "文件内容", ... }
        """
        prompts = {}
        if not os.path.exists(self.prompts_dir):
            return prompts

        try:
            files = os.listdir(self.prompts_dir)
            # 排序，保证列表顺序一致
            files.sort()
            
            for filename in files:
                if filename.lower().endswith('.txt'):
                    name = os.path.splitext(filename)[0] # 去掉 .txt
                    path = os.path.join(self.prompts_dir, filename)
                    
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            prompts[name] = content
                            
            return prompts
        except Exception as e:
            print(f"❌ Error loading prompts: {e}")
            return {}
            
    def get_prompt_names(self) -> List[str]:
        """获取所有 Prompt 的名称列表"""
        return list(self.load_prompts().keys())