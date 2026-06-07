"""AgentWorkflow — durable ReAct loop with human-in-the-loop support.

The Agent is configured at worker startup (system_prompt, MCP servers, model)
and stored in agent_config. This workflow just drives the Runner loop and
wires up the ask_user / provide_user_input signal pair for HITL pauses.
"""

from __future__ import annotations

from temporalio import workflow
from temporalio.contrib.openai_agents.workflow import stateless_mcp_server

with workflow.unsafe.imports_passed_through():
    # Pre-import pydantic internals so the sandbox snapshots them before the
    # first workflow task — avoids "Module X imported after initial workflow
    # load" warnings when the Agents SDK constructs pydantic models.
    __import__("annotated_types")
    import pydantic_core
    import pydantic_core.core_schema  # noqa: F401
    from agents import Agent, Runner, function_tool

    import agent_config


@workflow.defn
class AgentWorkflow:
    def __init__(self) -> None:
        self._input_needed: bool = False
        self._question: str = ""
        self._user_input: str = ""

    @workflow.run
    async def run(self, execution_id: str) -> str:
        @function_tool
        async def ask_user(question_text: str) -> str:
            """Ask the human a question when clarification or approval is needed.

            Args:
                question_text: The question or approval request to present to the user.
            """
            self._question = question_text
            self._input_needed = True
            workflow.logger.info("[%s] waiting for user input: %s", execution_id, question_text)

            await workflow.wait_condition(lambda: not self._input_needed)

            workflow.logger.info("[%s] resumed", execution_id)
            answer = self._user_input
            self._question = ""
            self._user_input = ""
            return answer

        mcp_servers = [
            stateless_mcp_server(name=name, cache_tools_list=True)
            for name in agent_config.mcp_server_names
        ]

        agent = Agent(
            name="Agent",
            instructions=agent_config.system_prompt,
            model=agent_config.model,
            mcp_servers=mcp_servers,
            tools=[ask_user],
        )

        result = await Runner.run(agent, input=agent_config.effective_prompt)
        return str(result.final_output)

    @workflow.signal
    def provide_user_input(self, user_input: str) -> None:
        """Deliver the user's response to a pending ask_user call."""
        self._user_input = user_input
        self._input_needed = False

    @workflow.query
    def is_input_needed(self) -> bool:
        return self._input_needed

    @workflow.query
    def get_pending_question(self) -> str:
        return self._question
