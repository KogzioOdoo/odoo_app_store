"""Server-only transition capability; an RPC context cannot forge this object."""
INTERNAL_TRANSITION = object()
INTERNAL_CONTEXT_KEY = '_activity_management_transition'

class SchedulingValues:
    """A trusted, server-created scheduling payload (not an RPC dictionary)."""

    def __init__(self, values):
        self.values = values

def internal(records):
    return records.with_context(**{INTERNAL_CONTEXT_KEY: INTERNAL_TRANSITION})

def is_internal(records):
    return records.env.su or records.env.context.get(INTERNAL_CONTEXT_KEY) is INTERNAL_TRANSITION

def is_transition(records):
    return records.env.context.get(INTERNAL_CONTEXT_KEY) is INTERNAL_TRANSITION
