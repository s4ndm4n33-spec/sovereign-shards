"""Tests for circuit breaker (app.agent.circuit_breaker)."""

import unittest

from app.agent.circuit_breaker import CircuitBreaker, MAX_REPEAT_CALLS, MAX_STEP_TURNS


class TestCircuitBreaker(unittest.TestCase):

    def setUp(self):
        self.cb = CircuitBreaker()

    def test_healthy_initially(self):
        self.assertTrue(self.cb.is_healthy)

    def test_repeat_call_trips(self):
        for _ in range(MAX_REPEAT_CALLS):
            self.cb.record_turn(tool="run_read", args="same_file.py")
        trip = self.cb.check()
        self.assertIsNotNone(trip)
        self.assertEqual(trip.reason, "repeat_call")

    def test_varied_calls_no_trip(self):
        for i in range(MAX_REPEAT_CALLS):
            self.cb.record_turn(tool="run_read", args=f"file_{i}.py")
        self.assertIsNone(self.cb.check())

    def test_repeat_error_trips(self):
        # Use different args each time so repeat_call doesn't fire first
        for i in range(3):
            self.cb.record_turn(
                tool=f"run_tool_{i}", args=f"arg_{i}",
                output="[TOOL ERROR] permission denied",
                is_error=True,
            )
        trip = self.cb.check()
        self.assertIsNotNone(trip)
        self.assertEqual(trip.reason, "repeat_error")

    def test_step_turn_limit(self):
        for _ in range(MAX_STEP_TURNS):
            self.cb.record_turn(tool=f"tool_{_}", args=str(_))
        trip = self.cb.check()
        self.assertIsNotNone(trip)
        self.assertEqual(trip.reason, "step_stuck")

    def test_reset_step(self):
        for _ in range(MAX_STEP_TURNS - 1):
            self.cb.record_turn(tool=f"tool_{_}", args=str(_))
        self.cb.reset_step()
        self.assertIsNone(self.cb.check())

    def test_stats(self):
        self.cb.record_turn(tool="run_read", args="f.py")
        stats = self.cb.stats()
        self.assertEqual(stats["total_turns"], 1)
        self.assertIn("run_read", stats["recent_tools"])

    def test_force_skip_after_multiple_trips(self):
        # Trip it 3 times
        for _ in range(3):
            for _ in range(MAX_REPEAT_CALLS):
                self.cb.record_turn(tool="run_read", args="same.py")
            trip = self.cb.check()
        self.assertIsNotNone(trip)
        self.assertTrue(trip.should_force_skip)

    def test_recovery_prompt_format(self):
        for _ in range(MAX_REPEAT_CALLS):
            self.cb.record_turn(tool="run_read", args="same.py")
        trip = self.cb.check()
        self.assertIn("[CIRCUIT BREAKER]", trip.recovery_prompt)


if __name__ == "__main__":
    unittest.main()
