"""
PPTAgent 环境变量配置加载模块

统一从 .env 文件和环境变量加载所有配置
替代原来的 config.yaml 和 mcp.json
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class EnvConfig:
    """环境变量配置类 - 统一管理所有配置"""
    
    # ==================== 核心 LLM 配置 ====================
    PPTAGENT_MODEL: str = "doubao-seed-1-8-251228"
    PPTAGENT_API_KEY: Optional[str] = None
    PPTAGENT_API_BASE: Optional[str] = None
    
    # ==================== 搜索配置 ====================
    TAVILY_API_KEY: Optional[str] = None
    TAVILY_BACKUP: Optional[str] = None
    
    # ==================== 数据库配置 ====================
    DATABASE_URL: Optional[str] = None
    
    # ==================== 工作空间配置 ====================
    WORKSPACE_BASE: str = "/tmp/ppt_workspace"
    
    # ==================== 知识库配置 ====================
    KNOWLEDGE_LLM_BASE_URL: Optional[str] = None
    KNOWLEDGE_LLM_API_KEY: Optional[str] = None
    KNOWLEDGE_LLM_MODEL: Optional[str] = None
    KNOWLEDGE_EMBEDDING_MODEL: Optional[str] = None
    
    # ==================== MinerU 配置 ====================
    MINERU_API_KEY: Optional[str] = None
    
    # ==================== DeepPresenter 配置 ====================
    # Design Agent - 用于PPT设计（唯一使用的Agent）
    DESIGN_AGENT_MODEL: Optional[str] = None
    DESIGN_AGENT_API_KEY: Optional[str] = None
    DESIGN_AGENT_BASE_URL: Optional[str] = None
    DESIGN_AGENT_MULTIMODAL: bool = True
    
    # ==================== 功能可用性标志 ====================
    DEEPPRESENTER_AVAILABLE: bool = False
    TAVILY_AVAILABLE: bool = False
    
    @classmethod
    def load(cls):
        """从环境变量加载所有配置"""
        logger.info("Loading configuration from environment variables...")
        
        # 核心配置
        cls.PPTAGENT_MODEL = os.getenv("PPTAGENT_MODEL", cls.PPTAGENT_MODEL)
        cls.PPTAGENT_API_KEY = os.getenv("PPTAGENT_API_KEY")
        cls.PPTAGENT_API_BASE = os.getenv("PPTAGENT_API_BASE")
        
        # 搜索配置
        cls.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
        cls.TAVILY_BACKUP = os.getenv("TAVILY_BACKUP")
        
        # 数据库配置
        cls.DATABASE_URL = os.getenv("DATABASE_URL")
        
        # 工作空间配置
        cls.WORKSPACE_BASE = os.getenv("WORKSPACE_BASE", cls.WORKSPACE_BASE)
        
        # 知识库配置
        cls.KNOWLEDGE_LLM_BASE_URL = os.getenv("KNOWLEDGE_LLM_BASE_URL")
        cls.KNOWLEDGE_LLM_API_KEY = os.getenv("KNOWLEDGE_LLM_API_KEY")
        cls.KNOWLEDGE_LLM_MODEL = os.getenv("KNOWLEDGE_LLM_MODEL")
        cls.KNOWLEDGE_EMBEDDING_MODEL = os.getenv("KNOWLEDGE_EMBEDDING_MODEL")
        
        # MinerU配置
        cls.MINERU_API_KEY = os.getenv("MINERU_API_KEY")
        
        # DeepPresenter配置（如果未设置，使用核心LLM配置作为fallback）
        cls.DESIGN_AGENT_MODEL = os.getenv("DESIGN_AGENT_MODEL") or cls.PPTAGENT_MODEL
        cls.DESIGN_AGENT_API_KEY = os.getenv("DESIGN_AGENT_API_KEY") or cls.PPTAGENT_API_KEY
        cls.DESIGN_AGENT_BASE_URL = os.getenv("DESIGN_AGENT_BASE_URL") or cls.PPTAGENT_API_BASE
        cls.DESIGN_AGENT_MULTIMODAL = os.getenv("DESIGN_AGENT_MULTIMODAL", "true").lower() == "true"
        
        # 初始化功能模块
        cls._init_deeppresenter()
        cls._init_tavily()
        
        # 打印配置状态
        cls._log_config_status()
    
    @classmethod
    def _init_deeppresenter(cls):
        """初始化 DeepPresenter 模块"""
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
            cls.TAVILY_AVAILABLE = False
    
    @classmethod
    def _log_config_status(cls):
        """打印配置状态"""
        logger.info("=" * 70)
        logger.info("PPTAgent Configuration Status")
        logger.info("=" * 70)
        logger.info(f"Core LLM Model: {cls.PPTAGENT_MODEL}")
        logger.info(f"Core LLM API: {'✓ Configured' if cls.PPTAGENT_API_KEY else '✗ Missing'}")
        logger.info(f"Tavily Search: {'✓ Available' if cls.TAVILY_AVAILABLE else '✗ Not available'}")
        logger.info(f"DeepPresenter: {'✓ Available' if cls.DEEPPRESENTER_AVAILABLE else '✗ Not available'}")
        logger.info(f"Database: {'✓ Configured' if cls.DATABASE_URL else '✗ Not configured'}")
        logger.info(f"Workspace: {cls.WORKSPACE_BASE}")
        logger.info("=" * 70)
    
    @classmethod
    def to_deeppresenter_config(cls) -> Dict[str, Any]:
        """
        转换为 DeepPresenter 兼容的配置格式
        用于替代 config.yaml
        注意：只返回真正使用的配置（design_agent）
        """
        return {
            "design_agent": {
                "base_url": cls.DESIGN_AGENT_BASE_URL,
                "model": cls.DESIGN_AGENT_MODEL,
                "api_key": cls.DESIGN_AGENT_API_KEY,
                "is_multimodal": cls.DESIGN_AGENT_MULTIMODAL,
            },
        }
    
    @classmethod
    def to_mcp_config(cls) -> list:
        """
        转换为 MCP 兼容的配置格式
        用于替代 mcp.json
        """
        return [
            {
                "name": "deeppresenter",
                "description": "DeepPresenter Tools",
                "command": "python",
                "args": ["/app/deeppresenter/deeppresenter/tools/server.py", "$WORKSPACE"],
                "env": {
                    "MINERU_API_KEY": cls.MINERU_API_KEY or "",
                    "TAVILY_API_KEY": cls.TAVILY_API_KEY or "",
                    "TAVILY_BACKUP": cls.TAVILY_BACKUP or "",
                    "LLM_CONFIG_FILE": "$LLM_CONFIG_FILE",
                }
            },
            {
                "name": "pptagent",
                "description": "https://github.com/icip-cas/PPTAgent",
                "command": "pptagent-mcp",
                "args": [],
                "env": {
                    "PPTAGENT_MODEL": cls.PPTAGENT_MODEL,
                    "PPTAGENT_API_KEY": cls.PPTAGENT_API_KEY or "",
                    "PPTAGENT_API_BASE": cls.PPTAGENT_API_BASE or "",
                }
            }
        ]


# 全局配置实例
env_config = EnvConfig()
