"""
PPTAgent 配置加载模块

从 config.yaml 和环境变量加载配置
"""

import os
import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# 配置文件可能的路径（Docker 和本地开发）
CONFIG_PATHS = [
    Path("/app/deeppresenter/deeppresenter/config.yaml"),  # Docker
    Path(__file__).parent.parent / "deeppresenter/deeppresenter/config.yaml",  # 本地
]

MCP_PATHS = [
    Path("/app/deeppresenter/deeppresenter/mcp.json"),  # Docker
    Path(__file__).parent.parent / "deeppresenter/deeppresenter/mcp.json",  # 本地
]


class Config:
    """全局配置类"""
    
    # 豆包 API 配置
    DOUBAO_API_KEY: Optional[str] = None
    DOUBAO_BASE_URL: Optional[str] = None
    DOUBAO_MODEL: Optional[str] = None
    
    # Tavily 搜索 API
    TAVILY_API_KEY: Optional[str] = None
    TAVILY_BACKUP: Optional[str] = None
    
    # DeepPresenter 配置
    GLOBAL_CONFIG: Optional[dict] = None
    
    # 功能可用性标志
    DEEPPRESENTER_AVAILABLE: bool = False
    SEARCH_AVAILABLE: bool = False
    TAVILY_AVAILABLE: bool = False
    
    @classmethod
    def load(cls):
        """加载所有配置"""
        cls._load_yaml_config()
        cls._load_env_config()
        cls._init_deeppresenter()
        cls._init_tavily()
        cls._log_config_status()
    
    @classmethod
    def _load_yaml_config(cls):
        """从 YAML 文件加载配置"""
        for config_path in CONFIG_PATHS:
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    
                    # 提取豆包 API 配置
                    llm_config = config.get('llm', {})
                    cls.DOUBAO_API_KEY = llm_config.get('api_key')
                    cls.DOUBAO_BASE_URL = llm_config.get('base_url')
                    cls.DOUBAO_MODEL = llm_config.get('model')
                    
                    # 提取 Tavily 配置
                    tavily_config = config.get('tavily', {})
                    if not cls.TAVILY_API_KEY:
                        cls.TAVILY_API_KEY = tavily_config.get('api_key')
                    
                    cls.GLOBAL_CONFIG = config
                    logger.info(f"✓ Loaded config from: {config_path}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load config from {config_path}: {e}")
    
    @classmethod
    def _load_env_config(cls):
        """从环境变量加载配置（覆盖 YAML）"""
        # 豆包 API
        if os.getenv("PPTAGENT_API_KEY"):
            cls.DOUBAO_API_KEY = os.getenv("PPTAGENT_API_KEY")
        if os.getenv("PPTAGENT_API_BASE"):
            cls.DOUBAO_BASE_URL = os.getenv("PPTAGENT_API_BASE")
        if os.getenv("PPTAGENT_MODEL"):
            cls.DOUBAO_MODEL = os.getenv("PPTAGENT_MODEL")
        
        # Tavily API
        if os.getenv("TAVILY_API_KEY"):
            cls.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
        if os.getenv("TAVILY_BACKUP"):
            cls.TAVILY_BACKUP = os.getenv("TAVILY_BACKUP")
    
    @classmethod
    def _init_deeppresenter(cls):
        """初始化 DeepPresenter"""
        try:
            import sys
            sys.path.insert(0, "/app/pptagent")
            sys.path.insert(0, "/app/deeppresenter")
            sys.path.insert(0, "/app")
            
            from deeppresenter.agents.slide_design import SlideDesign
            from deeppresenter.agents.env import AgentEnv
            from deeppresenter.utils.typings import InputRequest, PowerPointType, ConvertType, ChatMessage
            
            cls.DEEPPRESENTER_AVAILABLE = True
            logger.info("✓ DeepPresenter module loaded")
        except ImportError as e:
            logger.warning(f"✗ DeepPresenter not available: {e}")
            cls.DEEPPRESENTER_AVAILABLE = False
    
    @classmethod
    def _init_tavily(cls):
        """初始化 Tavily 搜索"""
        if cls.TAVILY_API_KEY:
            try:
                from tavily import TavilyClient
                cls.TAVILY_AVAILABLE = True
                logger.info("✓ Tavily search available")
            except ImportError:
                logger.warning("✗ Tavily package not installed")
                cls.TAVILY_AVAILABLE = False
        else:
            logger.warning("✗ Tavily API key not configured")
    
    @classmethod
    def _log_config_status(cls):
        """打印配置状态"""
        logger.info("=" * 60)
        logger.info("PPTAgent Configuration Status")
        logger.info("=" * 60)
        logger.info(f"Doubao API: {'✓ Configured' if cls.DOUBAO_API_KEY else '✗ Missing'}")
        logger.info(f"Doubao Model: {cls.DOUBAO_MODEL or 'Not set'}")
        logger.info(f"DeepPresenter: {'✓ Available' if cls.DEEPPRESENTER_AVAILABLE else '✗ Not available'}")
        logger.info(f"Tavily Search: {'✓ Available' if cls.TAVILY_AVAILABLE else '✗ Not available'}")
        logger.info("=" * 60)


# 导出配置实例
config = Config()
