from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date

from datetime import datetime, timedelta

from uuid import UUID
from talk2dom.db.session import get_db
from talk2dom.db.models import User
from talk2dom.db.models import (
    Project,
    ProjectMembership,
    ProjectInvite,
    APIUsage,
    UILocatorCache,
)
from talk2dom.api.deps import get_current_user
from talk2dom.api.schemas import (
    ProjectCreate,
    ProjectResponse,
    InviteRequest,
    MemberResponse,
    InviteResponse,
    ProjectUpdateRequest,
)

from loguru import logger

router = APIRouter()

member_limit = {
    "free": 1,
    "developer": 2,
    "pro": 10,
    "enterprise": float("inf"),
}


@router.post("", response_model=ProjectResponse)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    num_limit = {
        "free": 2,
        "developer": 10,
        "pro": float("inf"),
        "enterprise": float("inf"),
    }
    projects = (
        db.query(Project)
        .join(ProjectMembership, Project.id == ProjectMembership.project_id)
        .filter(ProjectMembership.user_id == current_user.id)
        .all()
    )
    if len(projects) >= num_limit.get(current_user.plan, 0):
        raise HTTPException(
            status_code=400,
            detail="Too many projects, please consider upgrade your plan",
        )

    project = Project(name=project_in.name, owner_id=current_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    membership = ProjectMembership(
        user_id=current_user.id, project_id=project.id, role="owner"
    )
    db.add(membership)
    db.commit()

    setattr(project, "member_count", 1)
    setattr(project, "api_calls", 0)
    setattr(project, "is_active", True)
    setattr(project, "owner_email", current_user.email)

    return project


@router.post("/{project_id}/invite")
def invite_user_to_project(
    project_id: UUID,
    invite: InviteRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    members = (
        db.query(ProjectMembership)
        .filter(
            ProjectMembership.project_id == project_id,
        )
        .all()
    )
    if len(members) >= member_limit.get(user.plan, 0):
        raise HTTPException(
            status_code=400,
            detail="Too many members under project, consider upgrade your plan",
        )

    # 检查是否已是成员
    existing_member = (
        db.query(ProjectMembership)
        .filter(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user.has(email=invite.email),
        )
        .first()
    )
    if existing_member:
        raise HTTPException(status_code=400, detail="User is already a member.")

    # 检查是否已有邀请记录
    existing_invite = (
        db.query(ProjectInvite)
        .filter(
            ProjectInvite.project_id == project_id, ProjectInvite.email == invite.email
        )
        .first()
    )
    if existing_invite:
        raise HTTPException(status_code=400, detail="User already invited.")

    new_invite = ProjectInvite(
        project_id=project_id, email=str(invite.email), invited_by_user_id=user.id
    )
    db.add(new_invite)
    db.commit()
    return {"detail": "Invitation sent."}


@router.get("/{project_id}/members")
def list_members(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1),
    offset: int = Query(default=0, ge=0),
):
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    membership = (
        db.query(ProjectMembership)
        .filter_by(user_id=current_user.id, project_id=project_id)
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=403, detail="You are not a member of this project"
        )

    members = (
        db.query(ProjectMembership, User)
        .join(User, ProjectMembership.user_id == User.id)
        .filter(ProjectMembership.project_id == project_id)
        .limit(limit)
        .offset(offset)
        .all()
    )
    total_count = (
        db.query(func.count(ProjectMembership.id))
        .filter(ProjectMembership.project_id == project_id)
        .scalar()
    )
    has_next = (offset + limit) < total_count
    items = [
        MemberResponse(user_id=u.id, email=u.email, role=m.role) for m, u in members
    ]
    return {"items": items, "has_next": has_next}


@router.get("")
def list_user_projects(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    limit: int = Query(default=10, ge=1),
    offset: int = Query(default=0, ge=0),
):
    projects = (
        db.query(Project)
        .join(ProjectMembership, Project.id == ProjectMembership.project_id)
        .filter(ProjectMembership.user_id == user.id)
        .limit(limit)
        .offset(offset)
        .all()
    )

    total_count = (
        db.query(func.count(Project.id))
        .join(ProjectMembership, Project.id == ProjectMembership.project_id)
        .filter(ProjectMembership.user_id == user.id)
        .scalar()
    )
    has_next = (offset + limit) < total_count

    items = []
    for project in projects:
        member_count = (
            db.query(ProjectMembership)
            .filter(ProjectMembership.project_id == project.id)
            .count()
        )
        api_calls = (
            db.query(func.count(APIUsage.id))
            .filter(
                APIUsage.project_id == project.id,
                APIUsage.status_code == 200,
            )
            .scalar()
        )
        owner = db.query(User).filter_by(id=project.owner_id).first()
        setattr(project, "owner_email", owner.email)
        if member_count > member_limit.get(owner.plan, 0):
            setattr(project, "is_active", False)
        else:
            setattr(project, "is_active", True)
        setattr(project, "member_count", member_count)
        setattr(project, "api_calls", api_calls)
        items.append(project)

    return {"items": items, "has_next": has_next}


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    project_update: ProjectUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    membership = (
        db.query(ProjectMembership)
        .filter_by(user_id=current_user.id, project_id=project_id)
        .first()
    )
    if not membership or membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can update the project")

    project.name = project_update.name
    db.commit()
    db.refresh(project)

    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    membership = (
        db.query(ProjectMembership)
        .filter_by(user_id=current_user.id, project_id=project_id)
        .first()
    )
    if not membership or membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can delete the project")

    db.query(ProjectMembership).filter_by(project_id=project_id).delete()
    db.query(ProjectInvite).filter_by(project_id=project_id).delete()

    db.delete(project)
    db.commit()
    return


@router.delete(
    "/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    project_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    membership = (
        db.query(ProjectMembership)
        .filter_by(user_id=current_user.id, project_id=project_id)
        .first()
    )
    if not membership or membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can remove members")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Owner cannot remove themselves")

    member_to_remove = (
        db.query(ProjectMembership)
        .filter_by(user_id=user_id, project_id=project_id)
        .first()
    )
    if not member_to_remove:
        raise HTTPException(status_code=404, detail="Member not found in project")

    db.delete(member_to_remove)

    # 删除相关 ProjectInvite 记录
    db.query(ProjectInvite).filter_by(
        invited_user_id=user_id, project_id=project_id
    ).delete()

    db.commit()
    return


@router.get("/{project_id}/invites")
def list_project_invites(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1),
    offset: int = Query(default=0, ge=0),
):
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    membership = (
        db.query(ProjectMembership)
        .filter_by(user_id=current_user.id, project_id=project_id)
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=403, detail="You are not a member of this project"
        )

    invites = (
        db.query(ProjectInvite)
        .filter_by(project_id=project_id)
        .limit(limit)
        .offset(offset)
        .all()
    )
    total_count = (
        db.query(func.count(ProjectInvite.id))
        .filter(ProjectInvite.project_id == project_id)
        .scalar()
    )
    has_next = (offset + limit) < total_count
    items = [
        InviteResponse(
            id=invite.id,
            email=invite.email,
            invited_by_user_id=invite.invited_by_user_id,
            created_at=invite.created_at,
            accepted=invite.accepted,
        )
        for invite in invites
    ]
    return {"items": items, "has_next": has_next}


@router.delete(
    "/{project_id}/invites/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_project_invite_by_user(
    project_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    membership = (
        db.query(ProjectMembership)
        .filter_by(user_id=current_user.id, project_id=project_id)
        .first()
    )
    if not membership or membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can remove invites")

    invite = (
        db.query(ProjectInvite).filter_by(project_id=project_id, id=user_id).first()
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    db.delete(invite)
    db.commit()
    return


@router.get("/{project_id}/api-usage")
def get_api_usage(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_member = (
        db.query(ProjectMembership)
        .filter_by(project_id=project_id, user_id=current_user.id)
        .first()
    )
    if not project_member:
        raise HTTPException(status_code=403, detail="Forbidden")

    start_date = datetime.utcnow() - timedelta(days=30)

    results = (
        db.query(
            cast(APIUsage.request_time, Date).label("date"),
            func.count().label("count"),
        )
        .filter(
            APIUsage.project_id == project_id,
            APIUsage.request_time >= start_date,
            APIUsage.status_code == 200,
        )
        .group_by(cast(APIUsage.request_time, Date))
        .order_by(cast(APIUsage.request_time, Date))
        .all()
    )
    logger.info(f"API usage for project {results}")

    return [{"timestamp": str(row.date), "count": row.count} for row in results]


@router.get("/{project_id}/locator-cache")
def list_locator_cache(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1),
    offset: int = Query(default=0, ge=0),
):
    project_member = (
        db.query(ProjectMembership)
        .filter_by(project_id=project_id, user_id=current_user.id)
        .first()
    )
    if not project_member:
        raise HTTPException(status_code=403, detail="Forbidden")

    locator_caches = (
        db.query(UILocatorCache)
        .filter_by(project_id=project_id)
        .order_by(UILocatorCache.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    # Get total count for pagination
    total_count = (
        db.query(func.count(UILocatorCache.id))
        .filter_by(project_id=project_id)
        .scalar()
    )
    has_next = (offset + limit) < total_count
    items = [
        {"id": cache.id, "url": cache.url, "user_instruction": cache.user_instruction}
        for cache in locator_caches
    ]
    return {
        "items": items,
        "has_next": has_next,
    }


@router.get("/{project_id}/locator-cache/{cache_id}")
def get_locator_cache(
    project_id: UUID,
    cache_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_member = (
        db.query(ProjectMembership)
        .filter_by(project_id=project_id, user_id=current_user.id)
        .first()
    )
    if not project_member:
        raise HTTPException(status_code=403, detail="Forbidden")

    locator_cache = (
        db.query(UILocatorCache)
        .filter_by(project_id=project_id, id=cache_id)
        .join(UILocatorCache.html)
        .first()
    )
    return {
        "html": locator_cache.html.row_html,
        "selector_type": locator_cache.selector_type,
        "selector_value": locator_cache.selector_value,
    }


@router.delete("/{project_id}/locator-cache/{cache_id}")
def delete_locator_cache(
    project_id: UUID,
    cache_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_member = (
        db.query(ProjectMembership)
        .filter_by(project_id=project_id, user_id=current_user.id)
        .first()
    )
    if not project_member:
        raise HTTPException(status_code=403, detail="Forbidden")

    locator_cache = (
        db.query(UILocatorCache).filter_by(project_id=project_id, id=cache_id).first()
    )
    db.delete(locator_cache)
    db.commit()
    return {
        "status": "success",
    }
