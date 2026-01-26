# main.py

import sys
import os
import json
import platform
# [统一] 全平台使用 pynput
from pynput import keyboard as pynput_keyboard
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QColor, QPainter
from PySide6.QtCore import QObject, Signal, Qt

from utils import LLM
from backend.sources.clipboard import ClipboardSource
from storage.local import LocalMarkdownStorage
from storage.feishu import FeishuDocStorage
from backend.manager import NoteManager
from backend.agent import KnowledgeAgent
from ui.window import FlashMemoWindow
from ui.chat_window import FlashChatWindow
from ui.worker import SaveWorker, UpdateWorker

CONFIG_FILE = "config.json"

# [适配] 仅用于决定首次生成的默认配置字符串
IS_MAC = platform.system() == 'Darwin'
# Mac 习惯用 Cmd, Windows 习惯用 Ctrl
DEFAULT_NOTE_KEY = "cmd+shift+space" if IS_MAC else "ctrl+shift+space"
DEFAULT_CHAT_KEY = "cmd+opt+space" if IS_MAC else "ctrl+alt+space"

DEFAULT_CONFIG = {
    "storage_type": "local",
    "hotkey": DEFAULT_NOTE_KEY,
    "chat_hotkey": DEFAULT_CHAT_KEY,
    "prompts_path": "./prompts",
    "feishu_app_id": "",
    "feishu_app_secret": "",
    "feishu_root_token": "",
    "openai_api_key": "",
    "openai_api_base": "",
    "openai_model": "gpt-3.5-turbo",
    "storage_path": "./my_notes_data"
}

def resolve_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def load_or_create_config():
    path = resolve_path(CONFIG_FILE)
    if not os.path.exists(path):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
        except Exception: pass
        return DEFAULT_CONFIG
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
            final_config = DEFAULT_CONFIG.copy()
            final_config.update(user_config)
            return final_config
    except Exception:
        return DEFAULT_CONFIG

# --- [核心] 统一的快捷键监听器 ---
class HotkeySignaler(QObject):
    trigger_signal = Signal()

    def __init__(self, hotkey_str):
        super().__init__()
        # 1. 转换格式 (ctrl -> <ctrl>)
        self.pynput_key_str = self._normalize_hotkey(hotkey_str)
        self.listener = None
        self.start_listening()

    def _normalize_hotkey(self, key_str):
        """
        将人类可读的 'ctrl+shift+space' 转换为 pynput 需要的 '<ctrl>+<shift>+<space>'
        """
        # 定义需要加尖括号的特殊键
        special_keys = {
            'ctrl', 'shift', 'alt', 'cmd', 'command', 'option', 'opt', 
            'space', 'enter', 'tab', 'esc', 'backspace', 'delete', 
            'up', 'down', 'left', 'right', 'f1' # 等等...
        }
        
        parts = key_str.lower().replace(' ', '').split('+')
        new_parts = []
        
        for p in parts:
            # 如果用户已经写了 <ctrl>，就不动
            if '<' in p and '>' in p:
                new_parts.append(p)
                continue
            
            # 兼容性映射
            if p == 'command': p = 'cmd'
            if p == 'opt' or p == 'option': p = 'alt' # pynput 中 Mac 的 Option 键通常对应 alt
            
            # 判断是否需要加尖括号
            # pynput 规则：修饰键和特殊键要加 <>，普通字母不需要
            if p in special_keys or p.startswith('f'):
                new_parts.append(f"<{p}>")
            else:
                new_parts.append(p)
                
        return "+".join(new_parts)

    def start_listening(self):
        try:
            # GlobalHotKeys 接收一个字典: { '<ctrl>+<alt>+h': callback }
            hotkey_map = {self.pynput_key_str: self.on_trigger}
            self.listener = pynput_keyboard.GlobalHotKeys(hotkey_map)
            # 非阻塞启动线程
            self.listener.start()
            print(f"✅ Hotkey registered: {self.pynput_key_str} (Raw: {self.raw_str if hasattr(self, 'raw_str') else 'Config'})")
        except Exception as e:
            print(f"❌ Hotkey Error: {e}")
            if IS_MAC:
                print("👉 Mac 用户请确保授予终端 '辅助功能' 权限。")

    def on_trigger(self):
        # 这里的回调是在 pynput 的线程中执行的
        # emit 是线程安全的，可以直接通知主线程 UI
        self.trigger_signal.emit()

    def stop(self):
        if self.listener:
            self.listener.stop()

def create_placeholder_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#8AB4F8"))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, 64, 64)
    painter.end()
    return QIcon(pixmap)

class AppController(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.config = load_or_create_config()
        self.worker = None 

        self.setup_storage()
        
        backup_dir = os.path.join(resolve_path(self.config['storage_path']), "backup")
        self.backup_storage = LocalMarkdownStorage(base_dir=backup_dir)

        self.setup_ai_source()
        
        prompts_path = resolve_path(self.config.get("prompts_path", "./prompts"))
        
        self.note_window = FlashMemoWindow(self.manager, prompts_dir=prompts_path)
        self.note_window.save_requested_signal.connect(self.handle_save_request) 
        self.note_window.update_requested_signal.connect(self.handle_update_request)

        agent_llm = self.create_llm_instance()
        self.knowledge_agent = KnowledgeAgent(self.main_storage, agent_llm, prompts_path)
        self.chat_window = FlashChatWindow(self.knowledge_agent)

        self.setup_tray()

        # 注册快捷键 (这里会自动进行格式转换)
        self.note_hotkey = HotkeySignaler(self.config.get("hotkey", DEFAULT_NOTE_KEY))
        self.note_hotkey.trigger_signal.connect(self.note_window.show_and_capture)
        
        self.chat_hotkey = HotkeySignaler(self.config.get("chat_hotkey", DEFAULT_CHAT_KEY))
        self.chat_hotkey.trigger_signal.connect(self.chat_window.toggle_window)

    def setup_storage(self):
        st_type = self.config.get("storage_type", "local").lower()
        path = resolve_path(self.config['storage_path'])
        if st_type == "feishu":
            try:
                self.main_storage = FeishuDocStorage(
                    self.config.get("feishu_app_id"), 
                    self.config.get("feishu_app_secret"), 
                    self.config.get("feishu_root_token")
                )
            except: self.main_storage = LocalMarkdownStorage(base_dir=path)
        else:
            self.main_storage = LocalMarkdownStorage(base_dir=path)

    def create_llm_instance(self):
        api_key = self.config.get("openai_api_key", "").strip()
        api_base = self.config.get("openai_api_base", "").strip() or None
        if api_key:
            return LLM(model_name=self.config.get("openai_model", "gpt-3.5-turbo"), api_key=api_key, api_url=api_base)
        return None

    def setup_ai_source(self):
        llm = self.create_llm_instance()
        source = ClipboardSource()
        source.llm = llm 
        self.manager = NoteManager(source=source, storage=self.main_storage)

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(create_placeholder_icon())
        
        menu = QMenu()
        act_note = QAction("Capture Note", self.app)
        act_note.triggered.connect(self.note_window.show_and_capture)
        menu.addAction(act_note)
        
        act_chat = QAction("Open Chat", self.app)
        act_chat.triggered.connect(self.chat_window.toggle_window)
        menu.addAction(act_chat)
        
        act_quit = QAction("Quit", self.app)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(act_quit)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def handle_save_request(self, note):
        self.backup_storage.save(note)
        print(f"💾 Backup saved.")
        self.worker = SaveWorker(self.main_storage, note)
        self.worker.finished_signal.connect(self.on_save_finished)
        self.worker.start()

    def handle_update_request(self, note):
        self.backup_storage.save(note) 
        print(f"💾 Update Backup saved.")
        self.worker = UpdateWorker(self.main_storage, note)
        self.worker.finished_signal.connect(self.on_update_finished)
        self.worker.start()

    def on_save_finished(self, success, msg):
        if not success:
            self.tray_icon.showMessage("Save Failed", f"Error: {msg}", QSystemTrayIcon.Warning, 5000)

    def on_update_finished(self, success, msg):
        if success:
            print(f"✅ Update Success: {msg}")
        else:
            print(f"❌ Update Failed: {msg}")
            self.tray_icon.showMessage("Update Failed", f"Error: {msg}", QSystemTrayIcon.Warning, 5000)

    def quit_app(self):
        self.note_hotkey.stop()
        self.chat_hotkey.stop()
        self.app.quit()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = AppController(app) 
    sys.exit(app.exec())

if __name__ == "__main__":
    main()