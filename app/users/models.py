from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Column, Integer, String, ForeignKey
from app.database import Base


class Teacher(Base):
    __tablename__ = "teachers"

    teacher_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    house = Column(String(100), unique=True, index=True, nullable=False)


class AuthUser(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "auth_users"
    username = Column(String(50), unique=True, index=True, nullable=False)
    permission = Column(String(50), nullable=True)
    card_number = Column(String(50), nullable=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    teacher = Column(Integer, ForeignKey("teachers.teacher_id"), nullable=True)


class User(Base):
    __tablename__ = "users"

    User_ID = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    lernbegleiter = Column(
        Integer, ForeignKey("sani_link_api.teachers.teacher_id"), nullable=True
    )
    karten_nummer = Column(String(255), nullable=True)
    permission = Column(String(255), nullable=True)
