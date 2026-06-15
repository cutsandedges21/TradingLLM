"""Phase 3 — quant factor zoo + IC/IR benchmarking (educational).

Cross-sectional alpha factors (classic + a faithful Kakushadze alpha101 subset)
scored by their Information Coefficient (IC) and IR against forward returns over a
universe of liquid names, then explained for learners.

    from trading_llm.factors import bench, explain, list_factors
    result = bench(period="2y", horizon=5)
    print(explain(result))
"""
from trading_llm.factors.runner import bench, BenchResult, DEFAULT_UNIVERSE, clean_universe
from trading_llm.factors.explain import explain
from trading_llm.factors.library import list_factors, get_factor

__all__ = ["bench", "BenchResult", "DEFAULT_UNIVERSE", "clean_universe",
           "explain", "list_factors", "get_factor"]
