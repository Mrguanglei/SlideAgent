"""
PPTAgent 环境变量配置加载模块

统一从 .env 文件和环境变量加载所有配置
替代原来的 config.yaml 和 mcp.json
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - fallback when dotenv is unavailable
    load_dotenv = None

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
    IMAGE_SEARCH_MAX: int = 10
    IMAGE_REFERENCE_MODEL: str = PPTAGENT_MODEL
    IMAGE_REFERENCE_API_KEY: Optional[str] = None
    IMAGE_REFERENCE_BASE_URL: Optional[str] = None
    IMAGE_REFERENCE_MAX_IMAGES: int = 12
    IMAGE_REFERENCE_CONCURRENCY: int = 3
    IMAGE_REFERENCE_TIMEOUT_SECONDS: int = 35
    IMAGE_REFERENCE_RETRIES: int = 1
    VISUAL_REVIEW_ENABLED: bool = True
    VISUAL_REVIEW_MIN_SCORE: int = 78
    VISUAL_REVIEW_MAX_ROUNDS: int = 1
    VISUAL_REVIEW_TIMEOUT_SECONDS: int = 30
    VISUAL_REWRITE_TIMEOUT_SECONDS: int = 40
    DECK_STYLE_REVIEW_ENABLED: bool = True
    DECK_STYLE_START_PAGE: int = 2
    DECK_STYLE_MIN_SCORE: int = 75
    DECK_STYLE_MAX_ROUNDS: int = 1
    DECK_STYLE_REVIEW_TIMEOUT_SECONDS: int = 28
    DECK_STYLE_REWRITE_TIMEOUT_SECONDS: int = 35
    
    # ==================== 数据库配置 ====================
    DATABASE_URL: Optional[str] = None
    
    # ==================== 工作空间配置 ====================
    WORKSPACE_BASE: str = "/tmp/ppt_workspace"

    # ==================== Web 安全配置 ====================
    CORS_ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    CORS_ALLOW_CREDENTIALS: bool = False
    CORS_ALLOWED_METHODS: List[str] = ["*"]
    CORS_ALLOWED_HEADERS: List[str] = ["*"]
    
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
    _LOADED: bool = False

    @classmethod
    def _ensure_dotenv_loaded(cls):
        """Best-effort load .env for local runs; do not override existing env vars."""
        if load_dotenv is None:
            return

        candidate_paths = [
            Path("/app/.env"),  # docker-compose mount path
            Path(__file__).resolve().parents[2] / ".env",  # repo root
            Path.cwd() / ".env",  # fallback to current working dir
        ]
        for dotenv_path in candidate_paths:
            if dotenv_path.exists():
                load_dotenv(dotenv_path=dotenv_path, override=False)
                logger.info("Loaded .env from %s", dotenv_path)
                return
    
    @classmethod
    def load(cls, force: bool = False):
        """从环境变量加载所有配置"""
        if cls._LOADED and not force:
            return
        logger.info("Loading configuration from environment variables...")
        cls._ensure_dotenv_loaded()
        
        # 核心配置
        cls.PPTAGENT_MODEL = os.getenv("PPTAGENT_MODEL", cls.PPTAGENT_MODEL)
        cls.PPTAGENT_API_KEY = os.getenv("PPTAGENT_API_KEY")
        cls.PPTAGENT_API_BASE = os.getenv("PPTAGENT_API_BASE")
        
        # 搜索配置
        cls.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
        cls.TAVILY_BACKUP = os.getenv("TAVILY_BACKUP")
        try:
            cls.IMAGE_SEARCH_MAX = int(os.getenv("IMAGE_SEARCH_MAX", cls.IMAGE_SEARCH_MAX))
        except Exception:
            cls.IMAGE_SEARCH_MAX = cls.IMAGE_SEARCH_MAX
        try:
            cls.IMAGE_REFERENCE_MAX_IMAGES = int(
                os.getenv("IMAGE_REFERENCE_MAX_IMAGES", cls.IMAGE_REFERENCE_MAX_IMAGES)
            )
        except Exception:
            cls.IMAGE_REFERENCE_MAX_IMAGES = cls.IMAGE_REFERENCE_MAX_IMAGES
        try:
            cls.IMAGE_REFERENCE_CONCURRENCY = int(
                os.getenv("IMAGE_REFERENCE_CONCURRENCY", cls.IMAGE_REFERENCE_CONCURRENCY)
            )
        except Exception:
            cls.IMAGE_REFERENCE_CONCURRENCY = cls.IMAGE_REFERENCE_CONCURRENCY
        try:
            cls.IMAGE_REFERENCE_TIMEOUT_SECONDS = int(
                os.getenv(
                    "IMAGE_REFERENCE_TIMEOUT_SECONDS",
                    cls.IMAGE_REFERENCE_TIMEOUT_SECONDS,
                )
            )
        except Exception:
            cls.IMAGE_REFERENCE_TIMEOUT_SECONDS = cls.IMAGE_REFERENCE_TIMEOUT_SECONDS
        try:
            cls.IMAGE_REFERENCE_RETRIES = int(
                os.getenv("IMAGE_REFERENCE_RETRIES", cls.IMAGE_REFERENCE_RETRIES)
            )
        except Exception:
            cls.IMAGE_REFERENCE_RETRIES = cls.IMAGE_REFERENCE_RETRIES
        cls.VISUAL_REVIEW_ENABLED = os.getenv(
            "VISUAL_REVIEW_ENABLED",
            str(cls.VISUAL_REVIEW_ENABLED),
        ).strip().lower() in {"1", "true", "yes", "on"}
        try:
            cls.VISUAL_REVIEW_MIN_SCORE = int(
                os.getenv("VISUAL_REVIEW_MIN_SCORE", cls.VISUAL_REVIEW_MIN_SCORE)
            )
        except Exception:
            cls.VISUAL_REVIEW_MIN_SCORE = cls.VISUAL_REVIEW_MIN_SCORE
        try:
            cls.VISUAL_REVIEW_MAX_ROUNDS = int(
                os.getenv("VISUAL_REVIEW_MAX_ROUNDS", cls.VISUAL_REVIEW_MAX_ROUNDS)
            )
        except Exception:
            cls.VISUAL_REVIEW_MAX_ROUNDS = cls.VISUAL_REVIEW_MAX_ROUNDS
        try:
            cls.VISUAL_REVIEW_TIMEOUT_SECONDS = int(
                os.getenv("VISUAL_REVIEW_TIMEOUT_SECONDS", cls.VISUAL_REVIEW_TIMEOUT_SECONDS)
            )
        except Exception:
            cls.VISUAL_REVIEW_TIMEOUT_SECONDS = cls.VISUAL_REVIEW_TIMEOUT_SECONDS
        try:
            cls.VISUAL_REWRITE_TIMEOUT_SECONDS = int(
                os.getenv("VISUAL_REWRITE_TIMEOUT_SECONDS", cls.VISUAL_REWRITE_TIMEOUT_SECONDS)
            )
        except Exception:
            cls.VISUAL_REWRITE_TIMEOUT_SECONDS = cls.VISUAL_REWRITE_TIMEOUT_SECONDS
        cls.DECK_STYLE_REVIEW_ENABLED = os.getenv(
            "DECK_STYLE_REVIEW_ENABLED",
            str(cls.DECK_STYLE_REVIEW_ENABLED),
        ).strip().lower() in {"1", "true", "yes", "on"}
        try:
            cls.DECK_STYLE_START_PAGE = int(
                os.getenv("DECK_STYLE_START_PAGE", cls.DECK_STYLE_START_PAGE)
            )
        except Exception:
            cls.DECK_STYLE_START_PAGE = cls.DECK_STYLE_START_PAGE
        try:
            cls.DECK_STYLE_MIN_SCORE = int(
                os.getenv("DECK_STYLE_MIN_SCORE", cls.DECK_STYLE_MIN_SCORE)
            )
        except Exception:
            cls.DECK_STYLE_MIN_SCORE = cls.DECK_STYLE_MIN_SCORE
        try:
            cls.DECK_STYLE_MAX_ROUNDS = int(
                os.getenv("DECK_STYLE_MAX_ROUNDS", cls.DECK_STYLE_MAX_ROUNDS)
            )
        except Exception:
            cls.DECK_STYLE_MAX_ROUNDS = cls.DECK_STYLE_MAX_ROUNDS
        try:
            cls.DECK_STYLE_REVIEW_TIMEOUT_SECONDS = int(
                os.getenv("DECK_STYLE_REVIEW_TIMEOUT_SECONDS", cls.DECK_STYLE_REVIEW_TIMEOUT_SECONDS)
            )
        except Exception:
            cls.DECK_STYLE_REVIEW_TIMEOUT_SECONDS = cls.DECK_STYLE_REVIEW_TIMEOUT_SECONDS
        try:
            cls.DECK_STYLE_REWRITE_TIMEOUT_SECONDS = int(
                os.getenv("DECK_STYLE_REWRITE_TIMEOUT_SECONDS", cls.DECK_STYLE_REWRITE_TIMEOUT_SECONDS)
            )
        except Exception:
            cls.DECK_STYLE_REWRITE_TIMEOUT_SECONDS = cls.DECK_STYLE_REWRITE_TIMEOUT_SECONDS
        
        # 数据库配置
        cls.DATABASE_URL = os.getenv("DATABASE_URL")
        
        # 工作空间配置
        cls.WORKSPACE_BASE = os.getenv("WORKSPACE_BASE", cls.WORKSPACE_BASE)

        # Web 安全配置
        cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS")
        if cors_origins_env:
            parsed_origins = [
                item.strip()
                for item in cors_origins_env.split(",")
                if item.strip()
            ]
            if parsed_origins:
                cls.CORS_ALLOWED_ORIGINS = parsed_origins

        cls.CORS_ALLOW_CREDENTIALS = (
            os.getenv("CORS_ALLOW_CREDENTIALS", str(cls.CORS_ALLOW_CREDENTIALS))
            .strip()
            .lower()
            in {"1", "true", "yes", "on"}
        )

        # CORS 安全防呆：allow_credentials=true 时不能使用通配来源
        if "*" in cls.CORS_ALLOWED_ORIGINS and cls.CORS_ALLOW_CREDENTIALS:
            logger.warning(
                "CORS configuration is unsafe ('*' with credentials). "
                "Forcing CORS_ALLOW_CREDENTIALS=False."
            )
            cls.CORS_ALLOW_CREDENTIALS = False
        
        # 知识库配置：强制复用 PPTAGENT 主配置，忽略历史分路变量残留
        cls.KNOWLEDGE_LLM_BASE_URL = cls.PPTAGENT_API_BASE
        cls.KNOWLEDGE_LLM_API_KEY = cls.PPTAGENT_API_KEY
        cls.KNOWLEDGE_LLM_MODEL = cls.PPTAGENT_MODEL
        cls.KNOWLEDGE_EMBEDDING_MODEL = os.getenv("KNOWLEDGE_EMBEDDING_MODEL")
        
        # MinerU配置
        cls.MINERU_API_KEY = os.getenv("MINERU_API_KEY")
        
        # DeepPresenter 配置：强制复用 PPTAGENT 主配置，忽略历史分路变量残留
        cls.DESIGN_AGENT_MODEL = cls.PPTAGENT_MODEL
        cls.DESIGN_AGENT_API_KEY = cls.PPTAGENT_API_KEY
        cls.DESIGN_AGENT_BASE_URL = cls.PPTAGENT_API_BASE
        cls.DESIGN_AGENT_MULTIMODAL = os.getenv("DESIGN_AGENT_MULTIMODAL", "true").lower() == "true"
        
        # 图像参考策略配置：模型可单独指定（多模态），其余仍复用 PPTAGENT 主配置
        image_reference_model = os.getenv("IMAGE_REFERENCE_MODEL")
        if image_reference_model and image_reference_model.strip():
            cls.IMAGE_REFERENCE_MODEL = image_reference_model.strip()
        else:
            cls.IMAGE_REFERENCE_MODEL = cls.PPTAGENT_MODEL
        cls.IMAGE_REFERENCE_API_KEY = cls.PPTAGENT_API_KEY
        cls.IMAGE_REFERENCE_BASE_URL = cls.PPTAGENT_API_BASE
        
        # 初始化功能模块
        cls._init_deeppresenter()
        cls._init_tavily()
        
        # 打印配置状态
        cls._log_config_status()
        cls._LOADED = True
    
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
        logger.info(f"Design Agent Model: {cls.DESIGN_AGENT_MODEL}")
        logger.info(f"Knowledge LLM Model: {cls.KNOWLEDGE_LLM_MODEL}")
        logger.info(
            (
                "Image Reference Model: %s (max_images=%s, concurrency=%s, "
                "timeout=%ss, retries=%s)"
            ),
            cls.IMAGE_REFERENCE_MODEL,
            cls.IMAGE_REFERENCE_MAX_IMAGES,
            cls.IMAGE_REFERENCE_CONCURRENCY,
            cls.IMAGE_REFERENCE_TIMEOUT_SECONDS,
            cls.IMAGE_REFERENCE_RETRIES,
        )
        logger.info(
            (
                "Visual Review: enabled=%s min_score=%s max_rounds=%s "
                "review_timeout=%ss rewrite_timeout=%ss"
            ),
            cls.VISUAL_REVIEW_ENABLED,
            cls.VISUAL_REVIEW_MIN_SCORE,
            cls.VISUAL_REVIEW_MAX_ROUNDS,
            cls.VISUAL_REVIEW_TIMEOUT_SECONDS,
            cls.VISUAL_REWRITE_TIMEOUT_SECONDS,
        )
        logger.info(
            (
                "Deck Style Review: enabled=%s start_page=%s min_score=%s "
                "max_rounds=%s review_timeout=%ss rewrite_timeout=%ss"
            ),
            cls.DECK_STYLE_REVIEW_ENABLED,
            cls.DECK_STYLE_START_PAGE,
            cls.DECK_STYLE_MIN_SCORE,
            cls.DECK_STYLE_MAX_ROUNDS,
            cls.DECK_STYLE_REVIEW_TIMEOUT_SECONDS,
            cls.DECK_STYLE_REWRITE_TIMEOUT_SECONDS,
        )
        logger.info(f"Core LLM API: {'✓ Configured' if cls.PPTAGENT_API_KEY else '✗ Missing'}")
        logger.info(
            "Image Reference API: %s",
            "✓ Configured" if cls.IMAGE_REFERENCE_API_KEY else "✗ Missing",
        )
        logger.info(f"Tavily Search: {'✓ Available' if cls.TAVILY_AVAILABLE else '✗ Not available'}")
        logger.info(f"Image Search Max: {cls.IMAGE_SEARCH_MAX}")
        logger.info(f"DeepPresenter: {'✓ Available' if cls.DEEPPRESENTER_AVAILABLE else '✗ Not available'}")
        logger.info(f"Database: {'✓ Configured' if cls.DATABASE_URL else '✗ Not configured'}")
        logger.info(f"Workspace: {cls.WORKSPACE_BASE}")
        logger.info(
            "CORS: origins=%s credentials=%s",
            cls.CORS_ALLOWED_ORIGINS,
            cls.CORS_ALLOW_CREDENTIALS,
        )
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
