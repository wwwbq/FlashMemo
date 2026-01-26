import time
import json
import requests
from openai import OpenAI


def retry(max_retries=3):
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        raise e
                    time.sleep(1 * retries)
        return wrapper
    return decorator


class LLM:
    def __init__(self, model_name, api_url=None, api_key=None):
        self.model_name = model_name
        self.api_url = api_url
        self.api_key = api_key
        self.history = []

    
    @retry(max_retries=3)
    def _chat_api(self, messages, mode="openai", generation_config=None):
        if mode == "requests":
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": self.model_name,
                "messages": messages,
                **(generation_config or {})
            }
            response = requests.post(self.api_url, headers=headers, json=data)
            return response.json()
        elif mode == "openai":
            if not hasattr(self, "client"):
                self.client = OpenAI(api_key=self.api_key, base_url=self.api_url)

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **(generation_config or {})
            )
            return response.choices[0].message.content


    def chat(self, prompt, use_history=False, mode="openai", generation_config=None):
        if use_history:
            self.history.append({"role": "user", "content": prompt})
            response = self._chat_api(self.history, mode, generation_config)
            self.history.append({"role": "assistant", "content": response})
        else:
            messages = [{"role": "user", "content": prompt}]
            response = self._chat_api(messages, mode, generation_config)
        return response
    

    def insert_system(self, system_message: list[str]):
        self.history = [{"role": "system", "content": msg} for msg in system_message] + self.history
    

    def export_history(self, remove_system: bool = False, export_mode: str = "json"):
        history_to_export = self.history
        if remove_system:
            history_to_export = [msg for msg in self.history if msg['role'] != 'system']
        
        if export_mode == "json":
            return json.dumps(history_to_export, indent=4)

        elif export_mode == "md":
            # 把对话数据按role和content格式化成markdown
            md_content = ""
            for msg in history_to_export:
                md_content += f"### {msg['role'].capitalize()}\n\n"
                md_content += f"{msg['content']}\n\n"
            return md_content
        
    
    def clear_history(self):
        self.history = []


    @property
    def history_messages(self):
        return self.history
    

    @property
    def has_system(self):
        return len(self.history) > 0 and self.history[0]['role'] == 'system'

