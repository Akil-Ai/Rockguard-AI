"""Clear all recorded data so a demo starts from a clean slate.

    python -m scripts.reset_demo

Drops every prediction, sensor reading, alert and image analysis. The trained
model artifact and the mine definition are untouched.
"""
from __future__ import annotations

from sqlalchemy import delete

from app.database import SessionLocal, init_db
from app.models import Alert, ImageAnalysis, Prediction, SensorReading


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        removed = {}
        for model in (Prediction, SensorReading, Alert, ImageAnalysis):
            removed[model.__tablename__] = db.execute(delete(model)).rowcount
        db.commit()
    finally:
        db.close()

    for table, n in removed.items():
        print(f"  cleared {n:>6} rows from {table}")
    print("Demo database reset.")


if __name__ == "__main__":
    main()
