

from deeppresenter.agents.agent import Agent
from deeppresenter.utils.typings import InputRequest, ChatMessage, Role
from deeppresenter.utils.log import info, warning


class SlideDesign(Agent):
    """
    使用以下工具：
    - think: 内部思考和规划
    - initialize_design: 初始化PPT设计
    - insert_page: 插入HTML页面
    - update_page: 修改页面
    - remove_pages: 删除页面
    - finalize: 完成生成
    """

    async def loop(self, req: InputRequest, markdown_file: str):
        """
        主循环：生成HTML幻灯片

        工作流程：
        1. 使用think工具分析和规划
        2. 调用initialize_design初始化PPT
        3. 逐页调用insert_page生成HTML
        4. 调用finalize完成
        """
        max_iterations = 50  # 防止无限循环
        no_tool_call_count = 0  # 连续没有工具调用的次数
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # 执行动作（LLM决策并调用工具）
            agent_message = await self.action(
                markdown_file=markdown_file,
                prompt=req.webagent_prompt
            )
            yield agent_message
            
            # 检查是否有工具调用
            tool_calls = self.chat_history[-1].tool_calls
            
            if not tool_calls:
                no_tool_call_count += 1
                warning(f"LLM did not return any tool calls (count: {no_tool_call_count})")
                
                # 检查消息内容是否表示完成
                content = ""
                if isinstance(agent_message.content, str):
                    content = agent_message.content
                elif isinstance(agent_message.content, list):
                    for block in agent_message.content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            content += block.get("text", "")
                
                # 如果消息包含完成相关的关键词，或者连续3次没有工具调用，自动结束
                completion_keywords = ["完成", "生成完毕", "已完成", "PPT生成完成", "所有页面"]
                is_completion_message = any(kw in content for kw in completion_keywords)
                
                if is_completion_message or no_tool_call_count >= 3:
                    info(f"Auto-finishing: completion_message={is_completion_message}, no_tool_count={no_tool_call_count}")
                    # 返回一个完成消息
                    yield ChatMessage(
                        role=Role.ASSISTANT,
                        content="✓ PPT生成完成！"
                    )
                    break
                
                continue
            
            # 重置计数器
            no_tool_call_count = 0
            
            # 执行工具调用
            outcome = await self.execute(tool_calls)

            if isinstance(outcome, list):
                # 多个工具调用结果
                for item in outcome:
                    yield item
            else:
                # 单个结果或完成信号
                # 如果调用了finalize，跳出循环
                last_tool = tool_calls[-1]
                if hasattr(last_tool, 'function') and last_tool.function.name == 'finalize':
                    yield outcome
                    break
                yield outcome
        
        if iteration >= max_iterations:
            warning(f"SlideDesign loop reached max iterations ({max_iterations})")
            yield ChatMessage(
                role=Role.ASSISTANT,
                content="✓ PPT生成完成！（达到最大迭代次数）"
            )
