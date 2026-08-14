from fastapi import APIRouter

from app.api import (
    actions,
    admin,
    behavior,
    bills,
    expenses,
    committees,
    debates,
    engage,
    issues,
    lookup,
    money,
    municipal,
    petitions,
    politicians,
    search,
    transparency,
    votes,
)


api_router = APIRouter(prefix="/v1")
api_router.include_router(search.router)
api_router.include_router(lookup.router)
api_router.include_router(actions.router)
api_router.include_router(engage.router)
api_router.include_router(issues.router)
api_router.include_router(money.router)
api_router.include_router(behavior.router)
api_router.include_router(expenses.router)
api_router.include_router(admin.router)
api_router.include_router(petitions.router)
api_router.include_router(municipal.router)
api_router.include_router(politicians.router)
api_router.include_router(votes.router)
api_router.include_router(bills.router)
api_router.include_router(committees.router)
api_router.include_router(debates.router)
api_router.include_router(transparency.router)
