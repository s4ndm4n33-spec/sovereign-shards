"""Tests for task graph (app.agent.graph)."""

import unittest

from app.agent.contracts import AgentStep
from app.agent.graph import topo_tiers, ready_steps, format_graph


class TestTopoTiers(unittest.TestCase):

    def test_linear_chain(self):
        steps = [
            AgentStep("a", "first", "done"),
            AgentStep("b", "second", "done", depends_on=("a",)),
            AgentStep("c", "third", "done", depends_on=("b",)),
        ]
        tiers = topo_tiers(steps)
        self.assertEqual(len(tiers), 3)
        self.assertEqual([s.id for s in tiers[0]], ["a"])
        self.assertEqual([s.id for s in tiers[1]], ["b"])
        self.assertEqual([s.id for s in tiers[2]], ["c"])

    def test_parallel_tier(self):
        steps = [
            AgentStep("a", "one", "done"),
            AgentStep("b", "two", "done"),
            AgentStep("c", "merge", "done", depends_on=("a", "b")),
        ]
        tiers = topo_tiers(steps)
        self.assertEqual(len(tiers), 2)
        tier0_ids = sorted(s.id for s in tiers[0])
        self.assertEqual(tier0_ids, ["a", "b"])
        self.assertEqual([s.id for s in tiers[1]], ["c"])

    def test_single_step(self):
        steps = [AgentStep("x", "solo", "done")]
        tiers = topo_tiers(steps)
        self.assertEqual(len(tiers), 1)
        self.assertEqual(len(tiers[0]), 1)

    def test_empty(self):
        self.assertEqual(topo_tiers([]), [])

    def test_cycle_raises(self):
        steps = [
            AgentStep("a", "one", "done", depends_on=("b",)),
            AgentStep("b", "two", "done", depends_on=("a",)),
        ]
        with self.assertRaises(ValueError):
            topo_tiers(steps)

    def test_diamond(self):
        steps = [
            AgentStep("a", "start", "done"),
            AgentStep("b", "left", "done", depends_on=("a",)),
            AgentStep("c", "right", "done", depends_on=("a",)),
            AgentStep("d", "merge", "done", depends_on=("b", "c")),
        ]
        tiers = topo_tiers(steps)
        self.assertEqual(len(tiers), 3)


class TestReadySteps(unittest.TestCase):

    def test_initial(self):
        steps = [
            AgentStep("a", "first", "done"),
            AgentStep("b", "second", "done", depends_on=("a",)),
        ]
        ready = ready_steps(steps, set())
        self.assertEqual([s.id for s in ready], ["a"])

    def test_after_first(self):
        steps = [
            AgentStep("a", "first", "done"),
            AgentStep("b", "second", "done", depends_on=("a",)),
        ]
        ready = ready_steps(steps, {"a"})
        self.assertEqual([s.id for s in ready], ["b"])

    def test_all_done(self):
        steps = [AgentStep("a", "first", "done")]
        ready = ready_steps(steps, {"a"})
        self.assertEqual(ready, [])


class TestFormatGraph(unittest.TestCase):

    def test_format(self):
        steps = [
            AgentStep("a", "read file", "done"),
            AgentStep("b", "fix bug", "done", depends_on=("a",)),
        ]
        output = format_graph(steps, completed={"a"})
        self.assertIn("✓", output)
        self.assertIn("○", output)
        self.assertIn("read file", output)


if __name__ == "__main__":
    unittest.main()
