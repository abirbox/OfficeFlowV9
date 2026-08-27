from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import os

async def check():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    
    docs = await db.dispatch_advance_salary.find({
        "officer_id": "6a8f56b0e2cab8da51c4d461",
        "client_id": "6a8f55eae2cab8da51c4d45c"
    }).to_list(100)
    
    print(f"Total docs in DB: {len(docs)}")
    for d in docs:
        print(f"  {d.get('type')}: ${d.get('amount')} - {d.get('note')} - source: {d.get('source', 'N/A')}")
    
    client.close()

asyncio.run(check())
