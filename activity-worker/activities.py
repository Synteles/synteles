from temporalio import activity


@activity.defn(name="call_llm_step")
async def call_llm_step(params: dict) -> dict:
    raise NotImplementedError("call_llm_step is not yet implemented")


@activity.defn(name="execute_tool")
async def execute_tool(params: dict) -> dict:
    raise NotImplementedError("execute_tool is not yet implemented")


@activity.defn(name="record_outcome")
async def record_outcome(params: dict) -> dict:
    raise NotImplementedError("record_outcome is not yet implemented")
