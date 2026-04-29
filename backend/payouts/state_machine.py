"""
Legal state transitions for payouts.

pending -> processing  (worker picks it up)
processing -> completed (bank confirms settlement)
processing -> failed    (bank declined or max retries exhausted)

All other transitions are explicitly illegal and raise InvalidStateTransition.
A failed payout returning funds is handled by NOT creating a debit ledger entry
for pending/processing payouts; failure simply removes the payout from the
"held" pool, releasing funds to available balance automatically.
"""

VALID_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["processing"],
    "processing": ["completed", "failed"],
}


class InvalidStateTransition(Exception):
    def __init__(self, from_status: str, to_status: str):
        super().__init__(
            f"Illegal payout state transition: {from_status!r} -> {to_status!r}"
        )
        self.from_status = from_status
        self.to_status = to_status


def assert_transition_allowed(current_status: str, next_status: str) -> None:
    """
    Raise InvalidStateTransition if the transition is not in VALID_TRANSITIONS.

    This is the single choke-point that enforces the state machine. Every status
    update goes through here so there is no way to move backwards (e.g.
    failed -> completed) without an explicit exception.
    """
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if next_status not in allowed:
        raise InvalidStateTransition(current_status, next_status)
