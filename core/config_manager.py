# config_manager.py - 配置管理模块
# 管理 API Key、模型列表、提示词模板等配置

import os
import json

# 配置文件路径
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
USER_CONFIG_PATH = os.path.join(CONFIG_DIR, "user_config.json")
PROMPTS_PATH = os.path.join(CONFIG_DIR, "prompts.json")

# 默认配置
DEFAULT_CONFIG = {
    "api_keys": [],
    "current_api_key": "",
    "current_model": "gemini-2.5-flash",
    "silent_mode": False,
    "auto_publish": True,
    "last_prompt_template": "深度科技主笔"
}

DEFAULT_MODELS = [
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]

class ConfigManager:
    def __init__(self):
        self.config = self.load_config()
        self.prompts = self.load_prompts()
        self.models = DEFAULT_MODELS
    
    # ================== 用户配置 ==================
    def load_config(self):
        """加载用户配置"""
        if os.path.exists(USER_CONFIG_PATH):
            try:
                with open(USER_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    for k, v in DEFAULT_CONFIG.items():
                        if k not in config:
                            config[k] = v
                    return config
            except:
                pass
        return DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """保存用户配置"""
        with open(USER_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        self.save_config()
    
    # ================== API Key 管理 ==================
    def get_api_keys(self):
        """获取所有已保存的 API Key"""
        return self.config.get("api_keys", [])
    
    def add_api_key(self, key):
        """添加新的 API Key"""
        keys = self.get_api_keys()
        if key and key not in keys:
            keys.append(key)
            self.config["api_keys"] = keys
            self.save_config()
    
    def get_current_api_key(self):
        return self.config.get("current_api_key", "")
    
    def set_current_api_key(self, key):
        self.set("current_api_key", key)
    
    # ================== 模型管理 ==================
    def get_models(self):
        return self.models
    
    def get_current_model(self):
        return self.config.get("current_model", self.models[0] if self.models else "")
    
    def set_current_model(self, model):
        self.set("current_model", model)
    
    # ================== 提示词模板 ==================
    def load_prompts(self):
        """加载提示词模板"""
        if os.path.exists(PROMPTS_PATH):
            try:
                with open(PROMPTS_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"templates": [], "last_used": ""}
    
    def save_prompts(self):
        """保存提示词模板"""
        with open(PROMPTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.prompts, f, ensure_ascii=False, indent=2)
    
    def get_prompt_templates(self):
        """获取所有模板名称"""
        return [t["name"] for t in self.prompts.get("templates", [])]
    
    def get_prompt_by_name(self, name):
        """根据名称获取模板"""
        for t in self.prompts.get("templates", []):
            if t["name"] == name:
                return t
        return None
    
    def save_prompt_template(self, name, description, prompt):
        """保存/更新模板"""
        templates = self.prompts.get("templates", [])
        # 查找是否存在
        for i, t in enumerate(templates):
            if t["name"] == name:
                templates[i] = {"name": name, "description": description, "prompt": prompt}
                self.prompts["templates"] = templates
                self.save_prompts()
                return
        # 新增
        templates.append({"name": name, "description": description, "prompt": prompt})
        self.prompts["templates"] = templates
        self.save_prompts()
    
    def delete_prompt_template(self, name):
        """删除模板"""
        templates = [t for t in self.prompts.get("templates", []) if t["name"] != name]
        self.prompts["templates"] = templates
        self.save_prompts()
    
    # ================== 发布设置 ==================
    def is_silent_mode(self):
        return self.config.get("silent_mode", False)
    
    def set_silent_mode(self, enabled):
        self.set("silent_mode", enabled)
    
    def is_auto_publish(self):
        return self.config.get("auto_publish", True)
    
    def set_auto_publish(self, enabled):
        self.set("auto_publish", enabled)
