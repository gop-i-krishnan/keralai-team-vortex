"""
backend/api/main.py
FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import (
    options, demo, config_router,
    match, booking, parse, viability, operator,
)
from backend.api.routers import compliance, warehouse_router, vessel, tracking, replan_router, cargo

app = FastAPI(
    title="JalSetu",
    description="AI waterway logistics orchestrator for Kerala — hackathon prototype",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(options.router,        prefix="/api")
app.include_router(demo.router,           prefix="/api")
app.include_router(config_router.router,  prefix="/api")
app.include_router(match.router,          prefix="/api")
app.include_router(booking.router,        prefix="/api")
app.include_router(parse.router,          prefix="/api")
app.include_router(viability.router,      prefix="/api")
app.include_router(operator.router,       prefix="/api")
app.include_router(compliance.router,     prefix="/api")
app.include_router(warehouse_router.router, prefix="/api")
app.include_router(vessel.router,           prefix="/api")
app.include_router(tracking.router,         prefix="/api")
app.include_router(replan_router.router,    prefix="/api")
app.include_router(cargo.router,            prefix="/api")


@app.get("/")
def root():
    return {"status": "ok", "service": "JalSetu"}
