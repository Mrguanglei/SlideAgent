"""
PPTAgent 分享服务模块

支持：
- 生成分享链接（包含完整对话历史）
- 分享链接访问
- 分享链接管理
"""

import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from database import crud

logger = logging.getLogger(__name__)


class ShareService:
    """分享服务 - 使用数据库存储完整对话"""

    def __init__(self):
        # 默认分享链接有效期（天）
        self.default_expire_days = 7

    async def create_share_link(
        self,
        db: AsyncSession,
        conversation_id: int,
        expire_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        创建分享链接（分享完整对话历史）

        Args:
            db: 数据库会话
            conversation_id: 对话 ID
            expire_days: 有效期（天），None 表示使用默认值

        Returns:
            分享信息 {share_id, expires_at}
        """
        # 生成唯一分享 ID
        share_id = str(uuid.uuid4())[:8]

        # 计算过期时间
        expire_days = expire_days or self.default_expire_days
        expires_at = datetime.utcnow() + timedelta(days=expire_days)

        # 保存到数据库
        share = await crud.create_share(
            db, share_id, conversation_id, expires_at
        )
        await db.commit()

        logger.info(f"Share link created: {share_id} for conversation {conversation_id}")

        return {
            "share_id": share_id,
            "expires_at": expires_at.isoformat(),
            "expire_days": expire_days
        }

    async def get_share_data(
        self,
        db: AsyncSession,
        share_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取分享数据（返回完整对话历史）

        Args:
            db: 数据库会话
            share_id: 分享 ID

        Returns:
            分享数据（包含完整对话），如果不存在或已过期返回 None
        """
        share = await crud.get_share_by_id(db, share_id)

        if not share:
            return None

        # 获取完整对话数据（使用conversations路由的相同逻辑）
        conversation = await crud.get_conversation(db, share.conversation_id)
        if not conversation:
            return None

        # 获取消息列表
        messages = await crud.get_messages(db, share.conversation_id)

        # 为每条消息获取关联的工具调用
        messages_with_tools = []
        for msg in messages:
            msg_dict = {
                "id": msg.id,
                "conversation_id": msg.conversation_id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
                "tool_calls": []
            }

            # 获取该消息的工具调用
            tool_calls = await crud.get_tool_calls_by_message(db, msg.id)
            for tc in tool_calls:
                tc_dict = {
                    "id": tc.id,
                    "tool_type": tc.tool_type,
                    "tool_name": tc.tool_name,
                    "status": tc.status,
                    "arguments": tc.arguments_json,
                    "result": tc.result_json,
                    "created_at": tc.created_at.isoformat()
                }

                # 根据工具类型加载关联数据
                if tc.tool_type == "web_search" or tc.tool_type == "search":
                    search_rounds = await crud.get_search_rounds_by_tool_call(db, tc.id)
                    tc_dict["search_rounds"] = []
                    for sr in search_rounds:
                        sr_dict = {
                            "id": sr.id,
                            "round_number": sr.round_number,
                            "query": sr.query,
                            "thinking": sr.thinking_content or "",
                            "results": []
                        }
                        results = await crud.get_search_results_by_round(db, sr.id)
                        sr_dict["results"] = [
                            {
                                "id": r.id,
                                "title": r.title,
                                "url": r.url,
                                "snippet": r.content[:200] if r.content else ""
                            }
                            for r in results
                        ]
                        tc_dict["search_rounds"].append(sr_dict)

                elif tc.tool_type == "task_plan":
                    task_plan = await crud.get_task_plan_by_tool_call(db, tc.id)
                    if task_plan:
                        tc_dict["task_plan"] = {
                            "id": task_plan.id,
                            "plan_content": task_plan.plan_content,
                            "steps": task_plan.steps_json
                        }

                msg_dict["tool_calls"].append(tc_dict)

            messages_with_tools.append(msg_dict)

        # 获取关联的 PPT 项目
        ppt_project = await crud.get_ppt_project_by_conversation(db, share.conversation_id)
        ppt_project_dict = None
        if ppt_project:
            # 获取最新版本
            latest_version = await crud.get_latest_ppt_version(db, ppt_project.id)
            slides = []
            if latest_version:
                slides_list = await crud.get_ppt_slides(db, latest_version.id)
                slides = [
                    {
                        "id": s.id,
                        "page_number": s.page_number,
                        "page_title": s.page_title,
                        "html_content": s.html_content
                    }
                    for s in slides_list
                ]

            ppt_project_dict = {
                "id": ppt_project.id,
                "title": ppt_project.title,
                "outline_content": ppt_project.outline_content,
                "slides": slides
            }

        await db.commit()  # 提交访问计数更新

        return {
            "conversation": {
                "id": conversation.id,
                "uuid": conversation.uuid,
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat(),
            },
            "messages": messages_with_tools,
            "ppt_project": ppt_project_dict,
            "share_info": {
                "share_id": share.share_id,
                "view_count": share.view_count,
                "created_at": share.created_at.isoformat(),
                "expires_at": share.expires_at.isoformat(),
            }
        }

    async def delete_share(
        self,
        db: AsyncSession,
        share_id: str
    ) -> bool:
        """
        删除分享链接

        Args:
            db: 数据库会话
            share_id: 分享 ID

        Returns:
            是否删除成功
        """
        success = await crud.delete_share(db, share_id)
        await db.commit()
        if success:
            logger.info(f"Share deleted: {share_id}")
        return success

    async def get_shares_by_conversation(
        self,
        db: AsyncSession,
        conversation_id: int
    ) -> List[Dict[str, Any]]:
        """
        获取对话的所有分享链接

        Args:
            db: 数据库会话
            conversation_id: 对话 ID

        Returns:
            分享链接列表
        """
        shares = await crud.get_shares_by_conversation(db, conversation_id)
        return [
            {
                "share_id": s.share_id,
                "created_at": s.created_at.isoformat(),
                "expires_at": s.expires_at.isoformat(),
                "view_count": s.view_count
            }
            for s in shares
        ]

    async def cleanup_expired(
        self,
        db: AsyncSession
    ) -> int:
        """
        清理过期的分享链接

        Args:
            db: 数据库会话

        Returns:
            清理的数量
        """
        count = await crud.cleanup_expired_shares(db)
        await db.commit()
        return count


# 单例实例
_share_service = ShareService()


async def create_share(
    db: AsyncSession,
    conversation_id: int,
    expire_days: Optional[int] = None
) -> Dict[str, Any]:
    """创建分享链接"""
    return await _share_service.create_share_link(
        db, conversation_id, expire_days
    )


async def get_share(
    db: AsyncSession,
    share_id: str
) -> Optional[Dict[str, Any]]:
    """获取分享数据"""
    return await _share_service.get_share_data(db, share_id)


async def delete_share(
    db: AsyncSession,
    share_id: str
) -> bool:
    """删除分享链接"""
    return await _share_service.delete_share(db, share_id)


async def get_conversation_shares(
    db: AsyncSession,
    conversation_id: int
) -> List[Dict[str, Any]]:
    """获取对话的所有分享链接"""
    return await _share_service.get_shares_by_conversation(db, conversation_id)
