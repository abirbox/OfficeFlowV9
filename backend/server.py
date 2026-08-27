from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, Request, Response, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import jwt
from datetime import datetime, timezone

from routes.auth import router as auth_router
from routes.companies import router as companies_router
from routes.employees import router as employees_router
from routes.attendance import router as attendance_router
from routes.gps import router as gps_router
from routes.tasks import router as tasks_router
from routes.leaves import router as leaves_router
from routes.admin import router as admin_router
from routes.shifts import router as shifts_router
from routes.shift_comments import router as shift_comments_router
from routes.overtime import router as overtime_router
from routes.payroll import router as payroll_router
from routes.notifications import router as notifications_router
from routes.settings import router as settings_router
from routes.office_locations import router as office_locations_router
from routes.reports import router as reports_router
from routes.dispatch import router as dispatch_router
from routes.dispatch_invoices import router as dispatch_invoices_router
from routes.so_payments import router as so_payments_router
from routes.presence import router as presence_router
from utils.auth import hash_password, verify_password
from utils.storage import init_storage, get_object
from utils.ws import manager
from models.dispatch import LEGACY_STATUS_MAP

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="OfficeFlow API", version="1.0.0")
api_router = APIRouter(prefix="/api")

app.state.db = db

async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")

    # Only create the bootstrap Super Admin on a completely empty
    # users collection. Do not recreate a manually deleted admin.
    user_count = await db.users.count_documents({})

    if user_count == 0:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hashed,
            "name": "Super Admin",
            "role": "super_admin",
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        })
        logger.info(f"Initial Super Admin created: {admin_email}")
    else:
        logger.info(
            f"Skipping default admin seed: {user_count} user(s) already exist"
        )

    credentials_content = f"""# OfficeFlow Test Credentials

## Admin Account
- Email: {admin_email}
- Password: {admin_password}
- Role: super_admin

## Auth Endpoints
- POST /api/auth/register - Register new user
- POST /api/auth/login - Login
- POST /api/auth/logout - Logout
- GET /api/auth/me - Get current user
- POST /api/auth/refresh - Refresh access token
- POST /api/auth/forgot-password - Request password reset
- POST /api/auth/reset-password - Reset password with token

## Test User Account (Create via register endpoint)
- Email: test@officeflow.com
- Password: Test@123
- Role: employee
"""

    try:
        with open("/app/memory/test_credentials.md", "w") as f:
            f.write(credentials_content)
        logger.info("Test credentials file updated")
    except Exception as e:
        logger.warning(f"Could not update test credentials file: {e}")

@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
        await db.login_attempts.create_index("identifier")
        # Dispatch indexes
        await db.dispatch_clients.create_index("name")
        await db.dispatch_vendors.create_index("name")
        await db.dispatch_officers.create_index("name")
        await db.dispatch_officers.create_index("vendor_id")
        await db.dispatch_post_sites.create_index("post_pin", unique=True)
        await db.dispatch_post_sites.create_index("client_id")
        # Prevent concurrent duplicate invoice numbers at the DB layer.
        try:
            await db.dispatch_invoices.create_index("invoice_number", unique=True)
        except Exception as e:
            # Duplicate rows in existing data would fail this — log and continue
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "Could not create unique index on dispatch_invoices.invoice_number: %s", e,
            )
        await db.dispatch_post_sites.create_index("vendor_id")
        await db.dispatch_schedules.create_index([("date", -1), ("officer_id", 1)])
        await db.dispatch_schedules.create_index("post_site_id")
        await db.dispatch_schedules.create_index("client_id")
        await db.dispatch_schedules.create_index("vendor_id")
        await db.dispatch_confirmation_history.create_index("schedule_id")
        await db.dispatch_action_history.create_index([("schedule_id", 1), ("at", -1)])
        await db.dispatch_audit.create_index([("at", -1)])
        await db.dispatch_audit.create_index("entity_type")
        await db.dispatch_audit.create_index("actor_id")
        await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
        await db.user_presence.create_index("user_id", unique=True)
        await db.user_presence.create_index("last_seen")
        await db.dispatch_advance_salary.create_index([("officer_id", 1), ("client_id", 1)])
        logger.info("Database indexes created")
        
        await seed_admin()

        # One-off migration: rename legacy shift-status labels in schedules
        # and their action history so both old and new records display the
        # new names ("Clocked In", "Complete", etc.).
        for old, new in LEGACY_STATUS_MAP.items():
            r1 = await db.dispatch_schedules.update_many(
                {"shift_status": old}, {"$set": {"shift_status": new}}
            )
            r2 = await db.dispatch_action_history.update_many(
                {"action": old}, {"$set": {"action": new}}
            )
            r3 = await db.dispatch_schedules.update_many(
                {"last_modified_action": old}, {"$set": {"last_modified_action": new}}
            )
            if r1.modified_count or r2.modified_count or r3.modified_count:
                logger.info(
                    f"Shift status migration: '{old}' -> '{new}' "
                    f"(schedules={r1.modified_count}, history={r2.modified_count}, "
                    f"last_modified_action={r3.modified_count})"
                )
        
        try:
            init_storage()
            logger.info("Storage initialized")
        except Exception as e:
            logger.warning(f"Storage initialization failed: {e}")
    except Exception as e:
        logger.error(f"Startup error: {e}")

@app.on_event("shutdown")
async def shutdown():
    client.close()

@api_router.get("/")
async def root():
    return {"message": "OfficeFlow API v1.0.0", "status": "running"}

@api_router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

api_router.include_router(auth_router)
api_router.include_router(companies_router)
api_router.include_router(employees_router)
api_router.include_router(attendance_router)
api_router.include_router(gps_router)
api_router.include_router(tasks_router)
api_router.include_router(leaves_router)
api_router.include_router(admin_router)
api_router.include_router(shifts_router)
api_router.include_router(shift_comments_router)
api_router.include_router(overtime_router)
api_router.include_router(payroll_router)
api_router.include_router(notifications_router)
api_router.include_router(settings_router)
api_router.include_router(office_locations_router)
api_router.include_router(reports_router)
api_router.include_router(dispatch_router)
api_router.include_router(dispatch_invoices_router)
api_router.include_router(so_payments_router)
api_router.include_router(presence_router)


@api_router.get("/files/{path:path}")
async def serve_file(path: str):
    """Public passthrough for objects stored in local filesystem storage so
    that <img src> works from the browser."""
    try:
        content, ctype = get_object(path)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(content=content, media_type=ctype,
                    headers={"Cache-Control": "public, max-age=86400"})


@api_router.websocket("/ws/dispatch")
async def ws_dispatch(websocket: WebSocket):
    """Real-time dispatch event stream. Authenticated via the access_token
    cookie (same-origin) or a ?token= query-param fallback."""
    from utils.auth import get_jwt_secret, JWT_ALGORITHM
    token = websocket.cookies.get("access_token") or websocket.query_params.get("token")
    user_id = None
    if token:
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") == "access":
                user_id = payload.get("sub")
        except Exception:
            user_id = None
    if not user_id:
        await websocket.close(code=1008)
        return
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception:
        manager.disconnect(user_id, websocket)


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[
        os.environ.get("FRONTEND_URL", "http://localhost:3000"),
        "http://localhost:3000",
    ],
    allow_origin_regex=r"https://.*\.preview\.emergentagent\.com",
    allow_methods=["*"],
    allow_headers=["*"],
)
