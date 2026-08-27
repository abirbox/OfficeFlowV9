"""Seed/remove 60 synthetic audit rows so the Audit Log pagination UI can be tested."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")


async def main(mode):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    if mode == "seed":
        base = datetime.now(timezone.utc) - timedelta(days=1)
        docs = [{
            "entity_type": "client",
            "entity_id": f"TESTPAGE{i}",
            "entity_name": f"TEST_PAGE Client {i:03d}",
            "action": "update",
            "actor_id": "testpage-actor",
            "actor_name": "QA Pagination Bot",
            "actor_role": "super_admin",
            "changes": {"city": "Dhaka"},
            "at": base - timedelta(minutes=i),
        } for i in range(60)]
        r = await db.dispatch_audit.insert_many(docs)
        print("seeded:", len(r.inserted_ids))
    else:
        r = await db.dispatch_audit.delete_many({"actor_id": "testpage-actor"})
        print("removed:", r.deleted_count)
    print("total audit docs:", await db.dispatch_audit.count_documents({}))


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "seed"))
