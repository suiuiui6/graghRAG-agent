"""
Data asset catalog endpoints — §5.2 of enterprise-evolution-blueprint.
"""

from fastapi import APIRouter, Query

from services.catalog import get_catalog

router = APIRouter()


@router.get("/catalog")
async def catalog_full():
    """Full data asset catalog with all statistical dimensions."""
    catalog = get_catalog()
    return catalog.build()


@router.get("/catalog/summary")
async def catalog_summary():
    """Lightweight catalog summary for dashboard cards."""
    catalog = get_catalog()
    return catalog.build_summary()


@router.get("/catalog/trends")
async def catalog_trends(days: int = Query(30, le=365)):
    """Trend data: entity growth, query volume, feedback rate."""
    catalog = get_catalog()
    return catalog.build_trends(days)


@router.get("/catalog/low-quality")
async def catalog_low_quality(threshold: float = Query(0.5, le=1.0)):
    """List documents/entities with quality below threshold."""
    catalog = get_catalog()
    return {"items": catalog.low_quality(threshold), "threshold": threshold}


@router.get("/catalog/entities")
async def catalog_entities(
    type: str | None = Query(None, alias="type"),
    project: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List entities filtered by type/project."""
    catalog = get_catalog()
    return catalog.list_entities(entity_type=type, limit=limit, offset=offset)


@router.get("/catalog/search")
async def catalog_search(
    q: str = Query(..., min_length=1),
    type: str | None = Query(None, alias="type"),
    limit: int = Query(50, le=200),
):
    """Cross-document entity search."""
    catalog = get_catalog()
    results = catalog.search_entities(q, entity_type=type, limit=limit)
    return {"query": q, "results": results, "total": len(results)}
