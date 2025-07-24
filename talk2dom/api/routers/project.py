from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from uuid import UUID
from talk2dom.db.session import get_db
from talk2dom.db.models import User
from talk2dom.db.models import Project, ProjectMembership, ProjectInvite
from talk2dom.api.deps import get_current_user, get_api_key_user
from talk2dom.api.schemas import (
    ProjectCreate,
    ProjectResponse,
    InviteRequest,
    MemberResponse,
)

router = APIRouter()


@router.post("/", response_model=ProjectResponse)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = Project(name=project_in.name, owner_id=current_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    membership = ProjectMembership(
        user_id=current_user.id, project_id=project.id, role="owner"
    )
    db.add(membership)
    db.commit()

    return project


@router.post("/projects/{project_id}/invite")
def invite_user_to_project(
    project_id: UUID,
    invite: InviteRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
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


@router.get("/{project_id}/members", response_model=list[MemberResponse])
def list_members(
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
    if not membership:
        raise HTTPException(
            status_code=403, detail="You are not a member of this project"
        )

    members = (
        db.query(ProjectMembership, User)
        .join(User, ProjectMembership.user_id == User.id)
        .filter(ProjectMembership.project_id == project_id)
        .all()
    )
    return [
        MemberResponse(user_id=u.id, email=u.email, role=m.role) for m, u in members
    ]


@router.get("/projects", response_model=List[ProjectResponse])
def list_user_projects(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    projects = (
        db.query(Project)
        .join(ProjectMembership, Project.id == ProjectMembership.project_id)
        .filter(ProjectMembership.user_id == user.id)
        .all()
    )
    return projects
