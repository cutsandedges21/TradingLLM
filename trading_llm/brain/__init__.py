"""The reasoning layer.

Phase 0 ships the unified provider router (``providers.ProviderRouter``) that
keeps the proven multi-key / multi-model fallback for the ``chat()`` path and
adds a ``get_llm()`` seam returning LangChain chat models for later phases.

Phase 1 will add ``brain/debate/`` (TradingAgents multi-agent pipeline) and
``brain/reflection/`` (learn-from-outcomes), both consuming ``get_llm()``.
"""
