"""
State machine tests: verify illegal transitions are blocked everywhere.
"""

from django.test import TestCase
from payouts.state_machine import assert_transition_allowed, InvalidStateTransition


class StateMachineTest(TestCase):
    def test_legal_transitions(self):
        assert_transition_allowed("pending", "processing")
        assert_transition_allowed("processing", "completed")
        assert_transition_allowed("processing", "failed")

    def test_illegal_transitions_raise(self):
        illegal = [
            ("pending", "completed"),
            ("pending", "failed"),
            ("completed", "pending"),
            ("completed", "processing"),
            ("completed", "failed"),
            ("failed", "pending"),
            ("failed", "processing"),
            ("failed", "completed"),
            ("processing", "pending"),
        ]
        for from_s, to_s in illegal:
            with self.assertRaises(InvalidStateTransition, msg=f"{from_s} -> {to_s} should raise"):
                assert_transition_allowed(from_s, to_s)
