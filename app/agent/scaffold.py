"""Scaffold: Registry Factory

Builds and configures the default tool registry for all J-Shard instances.
"""

from app.agent.tool_registry import ToolRegistry


def build_default_registry() -> ToolRegistry:
    """
    Factory function: Create and initialize the canonical tool registry.
    
    This is the single point where all tools are registered with the system.
    Modify this to add built-in tools.
    
    Usage:
        from app.agent.scaffold import build_default_registry
        registry = build_default_registry()
    
    Returns:
        ToolRegistry with all default tools registered
    """
    registry = ToolRegistry()
    
    # Register built-in tools here
    # Example:
    #   from app.agent.tools import SystemSnapshotTool
    #   registry.register_tool(SystemSnapshotTool())
    
    return registry
