from fastapi import APIRouter

from app.api import participants, test_designs, vocabulary


api_router = APIRouter(prefix="/api")
api_router.include_router(participants.router)
api_router.include_router(test_designs.router)
api_router.include_router(vocabulary.router)
