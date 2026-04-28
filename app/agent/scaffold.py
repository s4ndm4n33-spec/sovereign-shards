from app.agent.tool_registry import ToolRegistry

def build_default_registry() -> ToolRegistry:
    """The official factory for the Shard's toolset."""
    return ToolRegistry()
