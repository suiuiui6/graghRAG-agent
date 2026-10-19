"""
Domain Dictionary CRUD endpoints — §10.1 of enterprise-evolution-blueprint.
"""

from fastapi import APIRouter, HTTPException, Query

from domain_dict import DomainDict, get_domain_dict
from pydantic import BaseModel

router = APIRouter()
_dd: DomainDict | None = None


def _get() -> DomainDict:
    global _dd
    if _dd is None:
        _dd = get_domain_dict()
    return _dd


class TermCreate(BaseModel):
    term: str
    synonyms: list[str] = []
    abbreviations: list[str] = []
    related: list[str] = []
    entity_type: str | None = None
    category: str = "general"
    description: str = ""

class TermUpdate(BaseModel):
    synonyms: list[str] | None = None
    abbreviations: list[str] | None = None
    related: list[str] | None = None
    entity_type: str | None = None
    category: str | None = None
    description: str | None = None


@router.get("/domain-dict")
async def list_terms(category: str | None = Query(None)):
    dd = _get()
    return {"terms": dd.list_terms(category=category), "stats": dd.stats()}


@router.get("/domain-dict/search")
async def search_terms(q: str = Query(..., min_length=1)):
    dd = _get()
    return {"results": dd.search(q)}


@router.get("/domain-dict/{term}")
async def get_term(term: str):
    dd = _get()
    t = dd.get(term)
    if t is None:
        raise HTTPException(status_code=404, detail="Term not found")
    return t


@router.post("/domain-dict")
async def add_term(body: TermCreate):
    dd = _get()
    ok = dd.add(body.model_dump())
    if not ok:
        raise HTTPException(status_code=409, detail="Term already exists")
    return {"status": "created", "term": body.term}


@router.put("/domain-dict/{term}")
async def update_term(term: str, body: TermUpdate):
    dd = _get()
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    ok = dd.update(term, update_data)
    if not ok:
        raise HTTPException(status_code=404, detail="Term not found")
    return {"status": "updated", "term": term}


@router.delete("/domain-dict/{term}")
async def delete_term(term: str):
    dd = _get()
    ok = dd.delete(term)
    if not ok:
        raise HTTPException(status_code=404, detail="Term not found")
    return {"status": "deleted", "term": term}


@router.post("/domain-dict/import")
async def import_terms():
    dd = _get()
    count = dd.reload()
    return {"status": "reloaded", "count": count}
