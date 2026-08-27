from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone
from bson import ObjectId
import uuid

from models.gps_task import TaskCreate, TaskUpdate, TaskComment, SubtaskCreate, TaskResponse
from utils.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["Tasks"])

def get_db(request: Request):
    return request.app.state.db

async def build_task_response(task: dict, db) -> TaskResponse:
    project_name = None
    if task.get("project_id"):
        project = await db.projects.find_one({"id": task["project_id"]}, {"_id": 0})
        project_name = project.get("name") if project else None
    
    assignee_name = None
    if task.get("assigned_to"):
        try:
            assignee = await db.users.find_one({"_id": ObjectId(task["assigned_to"])}, {"password_hash": 0})
            assignee_name = assignee.get("name") if assignee else None
        except Exception:
            pass
    
    creator_name = None
    try:
        creator = await db.users.find_one({"_id": ObjectId(task["created_by"])}, {"password_hash": 0})
        creator_name = creator.get("name") if creator else None
    except Exception:
        pass
    
    return TaskResponse(
        id=task["id"],
        title=task["title"],
        description=task.get("description"),
        project_id=task.get("project_id"),
        project_name=project_name,
        assigned_to=task.get("assigned_to"),
        assignee_name=assignee_name,
        created_by=task["created_by"],
        creator_name=creator_name,
        status=task["status"],
        priority=task["priority"],
        labels=task.get("labels", []),
        due_date=task.get("due_date"),
        progress=task.get("progress", 0),
        work_type=task.get("work_type", "in_office"),
        comments=task.get("comments", []),
        subtasks=task.get("subtasks", []),
        attachments=task.get("attachments", []),
        created_at=task["created_at"].isoformat() if isinstance(task["created_at"], datetime) else task["created_at"],
        updated_at=task["updated_at"].isoformat() if task.get("updated_at") and isinstance(task["updated_at"], datetime) else task.get("updated_at"),
    )

@router.post("", response_model=TaskResponse)
async def create_task(task: TaskCreate, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    # Only admins/managers/hr can create tasks
    if user.get("role") not in ["super_admin", "admin", "hr", "manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to create tasks")
    
    task_doc = {
        "id": str(uuid.uuid4()),
        **task.model_dump(),
        "created_by": user["_id"],
        "progress": 0,
        "comments": [],
        "subtasks": [],
        "attachments": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    await db.tasks.insert_one(task_doc)
    return await build_task_response(task_doc, db)

@router.get("", response_model=list[TaskResponse])
async def get_tasks(
    request: Request,
    db = Depends(get_db),
    project_id: str = None,
    assigned_to: str = None,
    status: str = None,
    skip: int = 0,
    limit: int = 100,
):
    user = await get_current_user(request, db)
    
    query = {}
    # Employees can only see tasks assigned to them
    if user.get("role") == "employee":
        query["assigned_to"] = user["_id"]
    elif assigned_to:
        query["assigned_to"] = assigned_to
    
    if project_id:
        query["project_id"] = project_id
    if status:
        query["status"] = status
    
    tasks = await db.tasks.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return [await build_task_response(task, db) for task in tasks]

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Employees can only view tasks assigned to them
    if user.get("role") == "employee" and task.get("assigned_to") != user["_id"]:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return await build_task_response(task, db)

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, task: TaskUpdate, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    existing = await db.tasks.find_one({"id": task_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Employees can only update their own tasks (mainly status/progress)
    if user.get("role") == "employee" and existing.get("assigned_to") != user["_id"]:
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_data = {k: v for k, v in task.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.tasks.update_one({"id": task_id}, {"$set": update_data})
    
    updated = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    return await build_task_response(updated, db)

@router.delete("/{task_id}")
async def delete_task(task_id: str, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    if user.get("role") not in ["super_admin", "admin", "hr", "manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete tasks")
    
    existing = await db.tasks.find_one({"id": task_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    
    await db.tasks.delete_one({"id": task_id})
    return {"message": "Task deleted successfully"}

@router.post("/{task_id}/comments")
async def add_comment(task_id: str, comment: TaskComment, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    task = await db.tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    comment_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["_id"],
        "user_name": user["name"],
        "content": comment.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.tasks.update_one(
        {"id": task_id},
        {"$push": {"comments": comment_doc}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )
    
    return comment_doc

@router.get("/stats/overview")
async def get_task_stats(request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    total = await db.tasks.count_documents({})
    todo = await db.tasks.count_documents({"status": "todo"})
    in_progress = await db.tasks.count_documents({"status": "in_progress"})
    done = await db.tasks.count_documents({"status": "done"})
    
    return {
        "total": total,
        "todo": todo,
        "in_progress": in_progress,
        "done": done,
    }
