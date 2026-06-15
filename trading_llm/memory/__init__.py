"""Persistent local memory — the app's long-term market memory.

All state is plain JSON under the repo-root ``memory/`` folder, never
auto-deleted. Phase 0 ports the trader profile + journal and adds a small,
functional decision log that Phase 1's reflection loop (learn-from-outcomes)
will build on.
"""
