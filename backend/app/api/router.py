from fastapi import APIRouter

from app.api import (
    admin,
    behavior,
    bills,
    committees,
    debates,
    me,
    money,
    petitions,
    politicians,
    search,
    votes,
)


api_router = APIRouter(prefix="/v1")
api_router.include_router(search.router)
api_router.include_router(me.router)
api_router.include_router(money.router)
api_router.include_router(behavior.router)
api_router.include_router(admin.router)
api_router.include_router(petitions.router)
api_router.include_router(politicians.router)
api_router.include_router(votes.router)
api_router.include_router(bills.router)
api_router.include_router(committees.router)
api_router.include_router(debates.router)
