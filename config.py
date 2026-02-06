# 配置管理模块
import os
import json

# 配置目录
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# 默认配置
DEFAULT_CONFIG = {
    "api_key": "",
    "model": "gemini-3-flash-preview",
    "template": "tech_card",
    "prompt_style": "深度科技主笔",
    "proxy": {
        "enabled": False,
        "http": "",
        "https": ""
    },
    "theme": "dark",
    "auto_publish": False,
    "xhs_cookie": ""
}

# 可用模型列表
AVAILABLE_MODELS = [
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

# 可用模板列表
AVAILABLE_TEMPLATES = [
    ("tech_card", "科技卡片"),
    ("breath", "呼吸感"),
    ("cyber", "赛博朋克"),
    ("magazine", "杂志风"),
    ("quote_blue", "蓝色引号"),
    ("sticky", "便签风格"),
    ("card_blue", "蓝色卡片"),
    ("postit", "便利贴"),
    ("ticket", "票据风格"),
    ("receipt", "收据风格"),
    ("quote", "引用风格"),
    ("notion", "Notion风格"),
]

# Prompt 风格列表
PROMPT_STYLES = [
    ("深度科技主笔", "硬核冷峻，强认知冲击"),
    ("深度科技主笔亲和版", "去AI化核心，拟人风格"),
    ("轻松科普博主", "通俗易懂，有趣活泼"),
    ("XHS常用", "完整版深度科技"),
]


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """加载配置"""
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    # 合并默认配置（处理新增字段）
                    config = DEFAULT_CONFIG.copy()
                    config.update(saved)
                    return config
            except:
                pass
        return DEFAULT_CONFIG.copy()
    
    def save(self):
        """保存配置"""
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def get(self, key: str, default=None):
        """获取配置项"""
        return self.config.get(key, default)
    
    def set(self, key: str, value):
        """设置配置项"""
        self.config[key] = value
        self.save()
    
    def get_proxy(self) -> dict | None:
        """获取代理配置"""
        proxy = self.config.get("proxy", {})
        if proxy.get("enabled") and proxy.get("http"):
            return {
                "http": proxy.get("http"),
                "https": proxy.get("https") or proxy.get("http")
            }
        return None


# 全局配置实例
config = ConfigManager()
