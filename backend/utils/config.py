"""PPTAgent 配置加载模块（已废弃）

此模块已被 env_config.py 替代
请使用: from utils.env_config import env_config
"""

import logging
from utils.env_config import env_config

logger = logging.getLogger(__name__)

# 向后兼容：导入新的配置模块
# 旧代码可以继续使用 Config，但实际上使用的是 env_config


class ConfigMeta(type):
    """配置类的元类，用于动态代理属性访问"""
    
    def __getattribute__(cls, name):
        # 特殊方法和私有属性直接返回
        if name.startswith('_') or name in ('load', 'mro'):
            return super().__getattribute__(name)
        
        # 映射配置名（通用LLM配置）
        mapping = {
            # LLM配置
            'LLM_API_KEY': 'PPTAGENT_API_KEY',
            'LLM_BASE_URL': 'PPTAGENT_API_BASE',
            'LLM_MODEL': 'PPTAGENT_MODEL',
            # 其他配置
            'TAVILY_API_KEY': 'TAVILY_API_KEY',
            'TAVILY_BACKUP': 'TAVILY_BACKUP',
            'DEEPPRESENTER_AVAILABLE': 'DEEPPRESENTER_AVAILABLE',
            'TAVILY_AVAILABLE': 'TAVILY_AVAILABLE',
        }
        
        if name in mapping:
            return getattr(env_config, mapping[name])
        
        # 其他属性尝试从 env_config 获取
        try:
            return getattr(env_config, name)
        except AttributeError:
            return super().__getattribute__(name)


class Config(metaclass=ConfigMeta):
    """全局配置类（向后兼容包装器）"""
    
    @classmethod
    def load(cls):
        """加载所有配置"""
        env_config.load()


# 导出配置实例（向后兼容）
config = Config()
