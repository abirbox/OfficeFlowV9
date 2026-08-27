from fastapi import APIRouter, HTTPException, Response, Request, Depends
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import secrets
import os

from models.user import UserCreate, UserLogin, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from utils.auth import hash_password, verify_password, create_access_token, create_refresh_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

def get_db(request: Request):
    return request.app.state.db

async def check_brute_force(db, identifier: str) -> bool:
    attempts = await db.login_attempts.find_one({"identifier": identifier})
    if attempts:
        if attempts["count"] >= 5:
            lockout_until = attempts["locked_until"]
            if lockout_until and lockout_until > datetime.now(timezone.utc):
                raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")
    return True

async def record_failed_login(db, identifier: str):
    attempts = await db.login_attempts.find_one({"identifier": identifier})
    if attempts:
        new_count = attempts["count"] + 1
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=15) if new_count >= 5 else None
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$set": {"count": new_count, "locked_until": locked_until, "updated_at": datetime.now(timezone.utc)}}
        )
    else:
        await db.login_attempts.insert_one({
            "identifier": identifier,
            "count": 1,
            "locked_until": None,
            "updated_at": datetime.now(timezone.utc)
        })

async def clear_failed_attempts(db, identifier: str):
    await db.login_attempts.delete_one({"identifier": identifier})

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, request: Request, response: Response, db = Depends(get_db)):
    # Public self-registration is disabled - only admins can create accounts via /api/employees
    current = None
    try:
        current = await get_current_user(request, db)
        if current.get("role") not in ["super_admin", "admin", "hr"]:
            raise HTTPException(status_code=403, detail="Only admins can create accounts. Contact your administrator.")
    except HTTPException as e:
        if e.status_code == 401:
            raise HTTPException(status_code=403, detail="Public sign-up is disabled. Contact your administrator to get an account.")
        raise
    
    email_lower = user.email.lower()
    existing = await db.users.find_one({"email": email_lower})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    password_hash = hash_password(user.password)
    user_doc = {
        "email": email_lower,
        "password_hash": password_hash,
        "name": user.name,
        "role": user.role,
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    # Only set auth cookies for true self-signup (no current authenticated user).
    # Admin-initiated creation must NOT overwrite the admin's own session cookies.
    if current is None:
        access_token = create_access_token(user_id, email_lower, user.role)
        refresh_token = create_refresh_token(user_id)
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=315360000,
            path="/"
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=315360000,
            path="/"
        )
    
    return UserResponse(
        id=user_id,
        email=email_lower,
        name=user.name,
        role=user.role,
        status="active",
        created_at=user_doc["created_at"].isoformat()
    )

@router.post("/login", response_model=UserResponse)
async def login(credentials: UserLogin, request: Request, response: Response, db = Depends(get_db)):
    email_lower = credentials.email.lower()
    identifier = f"{request.client.host}:{email_lower}"
    
    await check_brute_force(db, identifier)
    
    user = await db.users.find_one({"email": email_lower})
    if not user or not verify_password(credentials.password, user["password_hash"]):
        await record_failed_login(db, identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    await clear_failed_attempts(db, identifier)
    
    user_id = str(user["_id"])
    access_token = create_access_token(user_id, email_lower, user.get("role", "employee"))
    refresh_token = create_refresh_token(user_id)
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=315360000,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=315360000,
        path="/"
    )
    
    return UserResponse(
        id=user_id,
        email=user["email"],
        name=user["name"],
        role=user.get("role", "employee"),
        phone=user.get("phone"),
        avatar_path=user.get("avatar_path"),
        company_id=user.get("company_id"),
        branch_id=user.get("branch_id"),
        department_id=user.get("department_id"),
        designation_id=user.get("designation_id"),
        permissions=user.get("permissions") or [],
        status=user.get("status", "active"),
        created_at=user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else user["created_at"]
    )

@router.post("/logout")
async def logout(response: Response, request: Request, db = Depends(get_db)):
    try:
        await get_current_user(request, db)
    except Exception:
        pass
    
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
async def get_me(request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    return UserResponse(
        id=user["_id"],
        email=user["email"],
        name=user["name"],
        role=user.get("role", "employee"),
        phone=user.get("phone"),
        avatar_path=user.get("avatar_path"),
        company_id=user.get("company_id"),
        branch_id=user.get("branch_id"),
        department_id=user.get("department_id"),
        designation_id=user.get("designation_id"),
        permissions=user.get("permissions") or [],
        status=user.get("status", "active"),
        created_at=user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else user["created_at"]
    )

@router.post("/refresh")
async def refresh_token(request: Request, response: Response, db = Depends(get_db)):
    import jwt
    from utils.auth import get_jwt_secret, JWT_ALGORITHM
    
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        user_id = str(user["_id"])
        access_token = create_access_token(user_id, user["email"], user.get("role", "employee"))
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=315360000,
            path="/"
        )
        
        return {"message": "Token refreshed"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db = Depends(get_db)):
    email_lower = data.email.lower()
    user = await db.users.find_one({"email": email_lower})
    if not user:
        return {"message": "If the email exists, a reset link has been sent"}
    
    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token": token,
        "email": email_lower,
        "used": False,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "created_at": datetime.now(timezone.utc)
    })
    
    reset_link = f"{os.environ.get('FRONTEND_URL')}/reset-password?token={token}"
    print(f"\n=== PASSWORD RESET LINK ===")
    print(f"Email: {email_lower}")
    print(f"Reset Link: {reset_link}")
    print(f"==========================\n")
    
    return {"message": "If the email exists, a reset link has been sent"}

@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db = Depends(get_db)):
    reset_token = await db.password_reset_tokens.find_one({"token": data.token})
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    if reset_token["used"]:
        raise HTTPException(status_code=400, detail="Reset token already used")
    
    if reset_token["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token expired")
    
    new_password_hash = hash_password(data.new_password)
    await db.users.update_one(
        {"email": reset_token["email"]},
        {"$set": {"password_hash": new_password_hash, "updated_at": datetime.now(timezone.utc)}}
    )
    
    await db.password_reset_tokens.update_one(
        {"token": data.token},
        {"$set": {"used": True}}
    )
    
    return {"message": "Password reset successfully"}