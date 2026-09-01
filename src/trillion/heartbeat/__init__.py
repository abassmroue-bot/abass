"""The heartbeat: a background loop that lets Trillion notice things
without being spoken to.

Kept deliberately separate from the conversation loop (`trillion.brain`)
— it doesn't matter whether it runs in the same process or a different
one, on this laptop or an always-on host later. See AGENT.md's Tier 5
section for the "quiet by default" rules this package is built around.
"""
