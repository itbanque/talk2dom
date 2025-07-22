from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, UniqueConstraint, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class UILocatorCache(Base):
    __tablename__ = "ui_locator_cache"

    id = Column(String, primary_key=True)
    user_instruction = Column(Text, nullable=False)
    html = Column(Text, nullable=False)
    selector_type = Column(String, nullable=False)
    selector_value = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
