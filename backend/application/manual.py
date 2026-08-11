"""手册检索用例。"""

from backend.infrastructure import manual_search as _manual_search


def search_manual(
    query: str,
    assetnum: str | None = None,
    top_k: int = 5,
    subsystem: str | None = None,
    fault_phenomenon: str | None = None,
) -> dict:
    """检索维修手册（委托 Infrastructure 实现）。"""
    return _manual_search.search_manual(
        query=query,
        assetnum=assetnum,
        subsystem=subsystem,
        fault_phenomenon=fault_phenomenon,
        top_k=top_k,
    )
