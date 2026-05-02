#--- SEAM START: DETERMINISTIC TOOL HARNESS ---#
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Tuple, List

from app.agent.contracts import ToolCall
from app.agent.scaffold import build_default_registry


@dataclass
class ToolTestCase:
    name: str
    tool: str
    args: Dict[str, Any]
    expect_success: bool
    expect_in_output: str


def run_test_case(registry, case: ToolTestCase) -> Tuple[bool, str]:
    success, output = registry.call_tool(
        ToolCall(name=case.tool, args=case.args)
    )

    if success != case.expect_success:
        return False, (
            f"[{case.name}] Expected success={case.expect_success}, "
            f"got {success}\nOutput: {output}"
        )

    if case.expect_in_output not in output:
        return False, (
            f"[{case.name}] Expected '{case.expect_in_output}' in output\n"
            f"Actual: {output}"
        )

    return True, f"[PASS] {case.name}"


def run_all_tests() -> int:
    registry = build_default_registry()

    
    #--- SEAM START: DEBUG TOOL DISCOVERY ---#
    print("\n[DEBUG] Discovered tools:")
    for name, meta in registry.list_tools().items():
        print(f"  - {name} ({meta['type']})")
    #--- SEAM END ---#
    
    
    
    test_cases: List[ToolTestCase] = [
        # --- Positive case (adjust to a REAL tool you have) ---
        ToolTestCase(
            name="valid_tool_execution",
            tool="scaffold",  # ← change to a real tool if needed
            args={},
            expect_success=True,
            expect_in_output="echo",  # substring match
        ),

        # --- Nonexistent tool ---
        ToolTestCase(
            name="tool_not_found",
            tool="does_not_exist",
            args={},
            expect_success=False,
            expect_in_output="not found",
        ),

        # --- Missing args (if you have such a tool) ---
        ToolTestCase(
            name="scaffold_missing_args",
            tool="scaffold",
            args={},
            expect_success=False,
            expect_in_output="error",  # argparse will emit error text
        )
    ]

    print("\n" + "=" * 60)
    print("DETERMINISTIC TOOL HARNESS")
    print("=" * 60)

    passed = 0

    for case in test_cases:
        ok, message = run_test_case(registry, case)
        print(message)
        if ok:
            passed += 1

    total = len(test_cases)

    print("\n" + "=" * 60)
    print(f"{passed}/{total} tests passed")

    return 0 if passed == total else 1

if __name__ == "__main__":
    raise SystemExit(run_all_tests())
#--- SEAM END ---#