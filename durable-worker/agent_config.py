# Module-level state populated by worker.py at startup and read by AgentWorkflow.
# Safe to read from the workflow: values are set once before the Worker polls and
# never mutated again, so they are consistent across all replay executions.

system_prompt: str = ""
effective_prompt: str = ""
mcp_server_names: list[str] = []
model: str = "gpt-4o"
