"""One-off cleanup: restore seeded 'Acme Corp' client (soft-deleted by QA test)
and remove the QA-created TEST_QA client document."""
import asyncio
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    r = await db.dispatch_clients.update_many(
        {"name": "Acme Corp"}, {"$set": {"status": "active"}}
    )
    print("Acme Corp restored:", r.modified_count)
    d = await db.dispatch_clients.delete_many({"name": {"$regex": "^TEST_QA"}})
    print("TEST_QA clients removed:", d.deleted_count)
    async for doc in db.dispatch_clients.find({}, {"name": 1, "status": 1}):
        print(doc.get("name"), doc.get("status"))


asyncio.run(main())
