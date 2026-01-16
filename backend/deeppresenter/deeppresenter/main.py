import json
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Literal

from deeppresenter.agents.env import AgentEnv
from deeppresenter.agents.slide_design import SlideDesign
from deeppresenter.utils.config import GLOBAL_CONFIG, DeepPresenterConfig
from deeppresenter.utils.constants import WORKSPACE_BASE
from deeppresenter.utils.log import debug, error, info, set_logger, timer
from deeppresenter.utils.typings import ChatMessage, ConvertType, InputRequest, Role
from deeppresenter.utils.webview import convert_html_to_pptx


class AgentLoop:
    def __init__(
        self,
        config: DeepPresenterConfig = GLOBAL_CONFIG,
        session_id: str | None = None,
        workspace: Path = None,
        language: Literal["zh", "en"] = "en",
    ):
        self.config = config
        self.language = language
        if session_id is None:
            session_id = str(uuid.uuid4())[:8]
        self.workspace = workspace or WORKSPACE_BASE / session_id
        self.intermediate_output = {}
        assert config.design_agent.is_multimodal or config.critic_agent is not None, (
            "Reflection requires a multimodal model or a separate critic agent"
        )
        set_logger(
            f"deeppresenter-loop-{self.workspace.stem}",
            self.workspace / "history" / "deeppresenter-loop.log",
        )
        debug(f"Initialized AgentLoop with workspace={self.workspace}")
        debug(f"Config: {self.config.model_dump_json(indent=2)}")

    @timer("DeepPresenter Loop")
    async def run(
        self,
        request: InputRequest,
        md_file: Path,
        hci_enable: bool = False,
        check_llms: bool = False,
        allow_reflection: bool = False,
    ) -> AsyncGenerator[str | ChatMessage, None]:
        """Main loop for DeepPresenter generation process.

        Note: This simplified version only supports SLIDE_DESIGN mode.
        Research and manuscript generation should be handled externally (e.g., in api_server.py).

        Arguments:
            request: InputRequest object containing task details.
            md_file: Path to the markdown manuscript file.
            hci_enable(not supported right now): Whether to enable human-computer interaction.
            check_llms: Whether to check LLM availability before running.
            allow_reflection: Whether to allow reflection in agents.
        Yields:
            ChatMessage or str: Messages or final output path.
        """
        if check_llms:
            self.config.validate_llms()
        with open(self.workspace / ".input_request.json", "w") as f:
            json.dump(request.model_dump(), f, ensure_ascii=False, indent=2)
        async with AgentEnv(self.workspace, self.config) as agent_env:
            self.agent_env = agent_env
            request.copy_to_workspace(self.workspace)
            hello_message = f"DeepPresenter running in {self.workspace}, generating slides from {md_file}"
            info(hello_message)
            yield ChatMessage(role=Role.SYSTEM, content=hello_message)

            # HTML幻灯片生成
            self.slide_design = SlideDesign(
                self.config,
                agent_env,
                self.workspace,
                self.language,
                allow_reflection,
            )
            try:
                async for msg in self.slide_design.loop(request, str(md_file)):
                    if isinstance(msg, str):
                        slide_html_dir = Path(msg)
                        if not slide_html_dir.is_absolute():
                            slide_html_dir = self.workspace / slide_html_dir
                        self.intermediate_output["slide_html_dir"] = slide_html_dir
                        break
                    yield msg
            except Exception as e:
                error_message = f"SlideDesign agent failed with error: {e}"
                error(error_message)
                yield ChatMessage(role=Role.SYSTEM, content=error_message)
                raise e
            finally:
                self.slide_design.save_history()
                self.save_results()

            pptx_path = self.workspace / f"{md_file.stem}.pptx"
            convert_html_to_pptx(
                slide_html_dir,
                pptx_path,
                aspect_ratio=request.aspect_ratio,
            )
            self.intermediate_output["pptx"] = pptx_path
            self.intermediate_output["final"] = str(pptx_path)
            msg = pptx_path

            self.save_results()
            info(f"DeepPresenter finished, final output at: {msg}")
            yield msg

    def save_results(self):
        with open(self.workspace / "intermediate_output.json", "w") as f:
            json.dump(
                {k: str(v) for k, v in self.intermediate_output.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )
