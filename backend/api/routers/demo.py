"""
backend/api/routers/demo.py
POST /demo/reset — restore in-memory state to seed.
GET  /demo/status — quick health check for demo.
"""
from fastapi import APIRouter
from backend import data_store as ds

router = APIRouter()


@router.post("/demo/reset")
def reset_demo():
    ds.reset()
    return {"status": "ok", "message": "Demo state reset to seed data"}


@router.get("/demo/status")
def demo_status():
    return {
        "nodes": len(ds.get_nodes()),
        "vessels": len(ds.get_vessels()),
        "sailings": len(ds.get_sailings()),
        "cargo": len(ds.get_cargo()),
        "bookings": len(ds.get_bookings()),
    }
