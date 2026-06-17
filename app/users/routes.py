import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_session
from app.users.auth import current_active_user, current_superuser
from app.users.manager import get_user_manager
from app.users.schemas import AuthUserCreate, AuthUserRead, TeacherCreate, TeacherRead
from app.users.models import AuthUser, Teacher, User


router = APIRouter()
auth_router = APIRouter()


@auth_router.post(
    "/register",
    response_model=AuthUserRead,
    status_code=status.HTTP_201_CREATED,
)
async def register_user_as_superuser(
    user_create: AuthUserCreate,
    user_manager=Depends(get_user_manager),
    _: AuthUser = Depends(current_superuser),
):
    created_user = await user_manager.create(user_create)
    return created_user


@router.get("/")
async def read_users(
    session: AsyncSession = Depends(get_session),
    user: AuthUser = Depends(current_active_user),
):
    if user.is_superuser:
        result = await session.execute(select(User))
        users = result.scalars().all()
        return users
    return {"message": "You are not a superuser."}


@router.patch("/admin/{user_id}")
async def make_user_admin(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    user: AuthUser = Depends(current_active_user),
):
    if not user.is_superuser:
        return {"message": "You are not a superuser."}

    result = await session.execute(select(AuthUser).where(AuthUser.id == user_id))
    target_user = result.scalar_one_or_none()

    if target_user is None:
        return {"message": "User not found."}

    target_user.is_superuser = 1
    await session.commit()
    return {"message": f"User {target_user.username} is now an admin."}


@router.delete("/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: AuthUser = Depends(current_superuser),
):
    result = await session.execute(select(AuthUser).where(AuthUser.id == user_id))
    target_user = result.scalar_one_or_none()

    if target_user is None:
        return {"message": "User not found."}

    await session.delete(target_user)
    await session.commit()
    return {"message": f"User {target_user.username} deleted."}


@router.get("/teachers")
async def read_teachers(
    session: AsyncSession = Depends(get_session),
    user=Depends(current_active_user),
) -> list[TeacherRead]:
    result = await session.execute(select(Teacher))
    teachers = result.scalars().all()
    return teachers


@router.post(
    "/teachers", response_model=TeacherRead, status_code=status.HTTP_201_CREATED
)
async def create_teacher(
    teacher: TeacherCreate,
    session: AsyncSession = Depends(get_session),
    _: AuthUser = Depends(current_superuser),
):
    db_teacher = Teacher(**teacher.model_dump())
    session.add(db_teacher)
    await session.commit()
    await session.refresh(db_teacher)
    return db_teacher


@router.delete("/teachers/{teacher_id}")
async def delete_teacher(
    teacher_id: int,
    session: AsyncSession = Depends(get_session),
    _: AuthUser = Depends(current_superuser),
):
    result = await session.execute(
        select(Teacher).where(Teacher.teacher_id == teacher_id)
    )
    target_teacher = result.scalar_one_or_none()

    if target_teacher is None:
        return {"message": "Teacher not found."}

    await session.delete(target_teacher)
    await session.commit()
    return {
        "message": f"Teacher {target_teacher.first_name} {target_teacher.last_name} deleted."
    }


@router.patch("/teachers/{teacher_id}")
async def update_teacher(
    teacher_id: int,
    teacher_update: TeacherCreate,
    session: AsyncSession = Depends(get_session),
    _: AuthUser = Depends(current_superuser),
):
    result = await session.execute(
        select(Teacher).where(Teacher.teacher_id == teacher_id)
    )
    target_teacher = result.scalar_one_or_none()

    if target_teacher is None:
        return {"message": "Teacher not found."}

    target_teacher.first_name = teacher_update.first_name
    target_teacher.last_name = teacher_update.last_name
    target_teacher.house = teacher_update.house

    await session.commit()
    await session.refresh(target_teacher)
    return target_teacher
