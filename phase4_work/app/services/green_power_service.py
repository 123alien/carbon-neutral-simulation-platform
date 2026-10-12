from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Enterprise, GreenPowerContract
from app.simulation.green_power import GreenPowerAllocator


class GreenPowerService:
    @staticmethod
    def create_contract(db: Session, data):
        if db.get(Enterprise, data.enterprise_id) is None: raise LookupError("enterprise not found")
        if data.end_at <= data.start_at: raise ValueError("end_at must be later than start_at")
        if data.purchase_kwh is None and data.purchase_share is None: raise ValueError("purchase_kwh or purchase_share is required")
        obj = GreenPowerContract(**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

    @staticmethod
    def list_contracts(db: Session, enterprise_id: int):
        return list(db.scalars(select(GreenPowerContract).where(GreenPowerContract.enterprise_id == enterprise_id).order_by(GreenPowerContract.start_at)).all())

    @staticmethod
    def allocator(db: Session, enterprise_id: int):
        rows = db.scalars(select(GreenPowerContract).where(GreenPowerContract.enterprise_id == enterprise_id, GreenPowerContract.status == "ACTIVE").order_by(GreenPowerContract.id)).all()
        return GreenPowerAllocator([{"start_at": row.start_at, "end_at": row.end_at, "purchase_kwh": row.purchase_kwh, "purchase_share": row.purchase_share, "emission_factor_kg_per_kwh": row.emission_factor_kg_per_kwh, "premium_per_kwh": row.premium_per_kwh} for row in rows]), len(rows)
