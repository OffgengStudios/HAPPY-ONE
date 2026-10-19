from fastapi import APIRouter, Response

from app.modules.iam.dependencies import Current, Database
from app.modules.search.schemas import SearchRequest, SearchResponse
from app.modules.search.service import search

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
def lookup(data: SearchRequest, db: Database, actor: Current, response: Response) -> SearchResponse:
    response.headers["Cache-Control"] = "no-store"
    return search(db, actor, data)
