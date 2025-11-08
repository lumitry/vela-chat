import logging
import time
import uuid
from typing import Optional

from open_webui.internal.db import Base, get_db


from open_webui.env import SRC_LOG_LEVELS
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, JSON, PrimaryKeyConstraint

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


####################
# Tag DB Schema
####################
class Tag(Base):
    __tablename__ = "tag"
    id = Column(String)
    name = Column(String)
    user_id = Column(String)
    meta = Column(JSON, nullable=True)

    # Unique constraint ensuring (id, user_id) is unique, not just the `id` column
    __table_args__ = (PrimaryKeyConstraint("id", "user_id", name="pk_id_user_id"),)


class TagModel(BaseModel):
    id: str
    name: str
    user_id: str
    meta: Optional[dict] = None
    model_config = ConfigDict(from_attributes=True)


####################
# Forms
####################


class TagChatIdForm(BaseModel):
    name: str
    chat_id: str


class TagTable:
    def insert_new_tag(self, name: str, user_id: str) -> Optional[TagModel]:
        with get_db() as db:
            id = name.replace(" ", "_").lower()
            tag = TagModel(**{"id": id, "user_id": user_id, "name": name})
            try:
                result = Tag(**tag.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return TagModel.model_validate(result)
                else:
                    return None
            except Exception as e:
                log.exception(f"Error inserting a new tag: {e}")
                return None

    def get_tag_by_name_and_user_id(
        self, name: str, user_id: str
    ) -> Optional[TagModel]:
        try:
            id = name.replace(" ", "_").lower()
            with get_db() as db:
                tag = db.query(Tag).filter_by(id=id, user_id=user_id).first()
                return TagModel.model_validate(tag)
        except Exception:
            return None

    def get_tags_by_user_id(self, user_id: str) -> list[TagModel]:
        with get_db() as db:
            return [
                TagModel.model_validate(tag)
                for tag in (db.query(Tag).filter_by(user_id=user_id).all())
            ]

    def get_tags_by_ids_and_user_id(
        self, ids: list[str], user_id: str
    ) -> list[TagModel]:
        with get_db() as db:
            return [
                TagModel.model_validate(tag)
                for tag in (
                    db.query(Tag).filter(Tag.id.in_(ids), Tag.user_id == user_id).all()
                )
            ]

    def delete_tag_by_name_and_user_id(self, name: str, user_id: str) -> bool:
        try:
            with get_db() as db:
                id = name.replace(" ", "_").lower()
                res = db.query(Tag).filter_by(id=id, user_id=user_id).delete()
                log.debug(f"res: {res}")
                db.commit()
                return True
        except Exception as e:
            log.error(f"delete_tag: {e}")
            return False

    def ensure_tags_exist(self, tag_names: list[str], user_id: str) -> None:
        """
        Ensure that all tags in the given list exist in the database.
        Creates any tags that don't exist yet.
        
        Args:
            tag_names: List of tag names (can be tag objects with 'name' property or strings)
            user_id: User ID to associate tags with
        """
        if not tag_names:
            return
        
        for tag_item in tag_names:
            # Handle both string tags and tag objects with 'name' property
            if isinstance(tag_item, str):
                tag_name = tag_item
            elif isinstance(tag_item, dict) and "name" in tag_item:
                tag_name = tag_item["name"]
            else:
                continue
            
            # Skip empty or invalid tag names
            if not tag_name or tag_name.lower() == "none":
                continue
            
            # Check if tag exists, create if it doesn't
            tag = self.get_tag_by_name_and_user_id(tag_name, user_id)
            if tag is None:
                self.insert_new_tag(tag_name, user_id)


Tags = TagTable()
