import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (challenges, home, ideas, knowledge, leaderboard, learning,
                      lms_admin, lms_analytics, lms_assessments, lms_assets,
                      lms_catalog, lms_certificates, reference, search)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s  %(message)s")

app = FastAPI(title="Minet Innovation Hub API (POC)", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)
for module in (reference, home, challenges, ideas, learning, leaderboard, knowledge, search,
               lms_catalog, lms_assessments, lms_certificates, lms_assets,
               lms_admin, lms_analytics):
    app.include_router(module.router)
