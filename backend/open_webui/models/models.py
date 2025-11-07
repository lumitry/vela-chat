import logging
import time
from typing import Optional

from open_webui.internal.db import Base, JSONField, get_db
from open_webui.env import SRC_LOG_LEVELS

from open_webui.models.users import Users, UserResponse
from open_webui.models.groups import Groups


from pydantic import BaseModel, ConfigDict

import sqlalchemy
from sqlalchemy import or_, and_, func, Index
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy import BigInteger, Column, Text, JSON, Boolean


from open_webui.utils.access_control import has_access


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


####################
# Models DB Schema
####################


# ModelParams is a model for the data stored in the params field of the Model table
class ModelParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    pass


# ModelMeta is a model for the data stored in the meta field of the Model table
class ModelMeta(BaseModel):
    profile_image_url: Optional[str] = "/static/favicon.png"

    description: Optional[str] = None
    """
        User-facing description of the model.
    """

    capabilities: Optional[dict] = None

    model_config = ConfigDict(extra="allow")

    pass


class Model(Base):
    __tablename__ = "model"

    id = Column(Text, primary_key=True)
    """
        The model's id as used in the API. If set to an existing model, it will override the model.
    """
    user_id = Column(Text)

    base_model_id = Column(Text, nullable=True)
    """
        An optional pointer to the actual model that should be used when proxying requests.
    """

    name = Column(Text)
    """
        The human-readable display name of the model.
    """

    params = Column(JSONField)
    """
        Holds a JSON encoded blob of parameters, see `ModelParams`.
    """

    meta = Column(JSONField)
    """
        Holds a JSON encoded blob of metadata, see `ModelMeta`.
    """

    access_control = Column(JSON, nullable=True)  # Controls data access levels.
    # Defines access control rules for this entry.
    # - `None`: Public access, available to all users with the "user" role.
    # - `{}`: Private access, restricted exclusively to the owner.
    # - Custom permissions: Specific access control for reading and writing;
    #   Can specify group or user-level restrictions:
    #   {
    #      "read": {
    #          "group_ids": ["group_id1", "group_id2"],
    #          "user_ids":  ["user_id1", "user_id2"]
    #      },
    #      "write": {
    #          "group_ids": ["group_id1", "group_id2"],
    #          "user_ids":  ["user_id1", "user_id2"]
    #      }
    #   }

    is_active = Column(Boolean, default=True)

    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


class ModelModel(BaseModel):
    id: str
    user_id: str
    base_model_id: Optional[str] = None

    name: str
    params: ModelParams
    meta: ModelMeta

    access_control: Optional[dict] = None

    is_active: bool
    updated_at: int  # timestamp in epoch
    created_at: int  # timestamp in epoch

    model_config = ConfigDict(from_attributes=True)


####################
# Forms
####################


class ModelUserResponse(ModelModel):
    user: Optional[UserResponse] = None


class ModelResponse(ModelModel):
    pass


class ModelMetadataResponse(BaseModel):
    """Lean response model with only essential fields for listing, excludes knowledge file data"""
    id: str
    user_id: str
    base_model_id: Optional[str] = None
    name: str
    meta: ModelMeta
    access_control: Optional[dict] = None
    is_active: bool
    updated_at: int
    created_at: int
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


class ModelForm(BaseModel):
    id: str
    base_model_id: Optional[str] = None
    name: str
    meta: ModelMeta
    params: ModelParams
    access_control: Optional[dict] = None
    is_active: bool = True


class ModelsTable:
    def insert_new_model(
        self, form_data: ModelForm, user_id: str
    ) -> Optional[ModelModel]:
        model = ModelModel(
            **{
                **form_data.model_dump(),
                "user_id": user_id,
                "created_at": int(time.time()),
                "updated_at": int(time.time()),
            }
        )
        try:
            with get_db() as db:
                result = Model(**model.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)

                if result:
                    return ModelModel.model_validate(result)
                else:
                    return None
        except Exception as e:
            log.exception(f"Failed to insert a new model: {e}")
            return None

    def get_all_models(self) -> list[ModelModel]:
        with get_db() as db:
            return [ModelModel.model_validate(model) for model in db.query(Model).all()]

    def get_models(self) -> list[ModelUserResponse]:
        """
        Get all models with associated user information.
        Optimized for performance with large datasets.
        """
        with get_db() as db:
            # Query all models with filter applied
            all_models = (
                db.query(Model)
                .filter(Model.base_model_id != None)
                .all()
            )
            
            # Early return if there are no models
            if not all_models:
                return []
                
            # Process in batches to improve memory usage
            batch_size = 50
            result = []
            
            # Get all user IDs in one go
            user_ids = {model.user_id for model in all_models if model.user_id}
            
            # Fetch all relevant users in a single query
            user_dict = {}
            if user_ids:
                users = Users.get_users_by_ids(list(user_ids))
                user_dict = {user.id: user for user in users}
            
            # Use a more efficient approach to model conversion
            # Process models in batches to limit memory usage with large datasets
            for i in range(0, len(all_models), batch_size):
                batch = all_models[i:i+batch_size]
                batch_result = []
                
                for model in batch:
                    user = user_dict.get(model.user_id)
                    
                    # Convert model to dict directly and add the user
                    model_dict = ModelModel.model_validate(model).model_dump()
                    model_dict["user"] = user.model_dump() if user else None
                    
                    # Add to batch result
                    batch_result.append(ModelUserResponse.model_validate(model_dict))
                
                # Add batch to final result
                result.extend(batch_result)
            
            return result

    def get_base_models(self) -> list[ModelModel]:
        with get_db() as db:
            return [
                ModelModel.model_validate(model)
                for model in db.query(Model).filter(Model.base_model_id == None).all()
            ]

    def get_models_by_user_id(
        self, user_id: str, permission: str = "write"
    ) -> list[ModelUserResponse]:
        with get_db() as db:
            start_time = time.time()
            
            # Step 1: Fetch user's group memberships once to use in access control
            user_groups = Groups.get_groups_by_member_id(user_id)
            user_group_ids = [group.id for group in user_groups]
            
            # Step 2: Fetch only the models that belong to this user directly
            user_models = (
                db.query(Model)
                .filter(Model.base_model_id != None)
                .filter(Model.user_id == user_id)
                .all()
            )
            
            # Step 3: Process models not owned by the user (with optimized access control)
            # This batch-processes access control instead of doing it one-by-one
            other_models = (
                db.query(Model)
                .filter(Model.base_model_id != None)
                .filter(Model.user_id != user_id)
                .all()
            )
            
            # Efficiently check access for all models at once 
            filtered_other_models = []
            for model in other_models:
                # Fast path: Public access if access_control is None
                if model.access_control is None:
                    if permission == "read":  # Public read access
                        filtered_other_models.append(model)
                    continue
                
                # Check permissions without making additional DB calls
                permission_access = model.access_control.get(permission, {})
                permitted_group_ids = permission_access.get("group_ids", [])
                permitted_user_ids = permission_access.get("user_ids", [])
                
                # User has direct access or through a group
                if (user_id in permitted_user_ids or 
                    any(g_id in permitted_group_ids for g_id in user_group_ids)):
                    filtered_other_models.append(model)
            
            # Combine user's models with filtered models
            all_models = user_models + filtered_other_models
            
            # Early return if no models found
            if not all_models:
                return []
            
            # Step 4: Get all user data needed for these models in one query
            user_ids = {model.user_id for model in all_models if model.user_id}
            
            user_dict = {}
            if user_ids:
                users = Users.get_users_by_ids(list(user_ids))
                user_dict = {user.id: user for user in users}
            
            # Step 5: Build response in batches to manage memory
            result = []
            batch_size = 50
            for i in range(0, len(all_models), batch_size):
                batch = all_models[i:i+batch_size]
                for model in batch:
                    model_owner = user_dict.get(model.user_id)
                    model_dict = ModelModel.model_validate(model).model_dump()
                    model_dict["user"] = model_owner.model_dump() if model_owner else None
                    result.append(ModelUserResponse.model_validate(model_dict))
            
            end_time = time.time()
            log.info(f"get_models_by_user_id took {(end_time - start_time):.3f} seconds for {len(all_models)} models")
            return result

    def get_models_metadata(self) -> list[ModelMetadataResponse]:
        """
        Get all models with only metadata (no knowledge file data).
        Optimized for listing pages that don't need full model data.
        """
        with get_db() as db:
            all_models = (
                db.query(Model)
                .filter(Model.base_model_id != None)
                .all()
            )
            
            if not all_models:
                return []
            
            # Get all user IDs in one go
            user_ids = {model.user_id for model in all_models if model.user_id}
            user_dict = {}
            if user_ids:
                users = Users.get_users_by_ids(list(user_ids))
                user_dict = {user.id: user for user in users}
            
            result = []
            batch_size = 50
            for i in range(0, len(all_models), batch_size):
                batch = all_models[i:i+batch_size]
                for model in batch:
                    user = user_dict.get(model.user_id)
                    
                    # Clean meta to remove knowledge file data
                    meta_dict = model.meta if model.meta else {}
                    cleaned_meta = {
                        "profile_image_url": meta_dict.get("profile_image_url", "/static/favicon.png"),
                        "description": meta_dict.get("description"),
                        "capabilities": meta_dict.get("capabilities"),
                    }
                    # Keep knowledge base references but not file data
                    if "knowledge" in meta_dict:
                        # If knowledge is a list, keep only IDs/names, not file data
                        knowledge = meta_dict.get("knowledge", [])
                        if isinstance(knowledge, list):
                            cleaned_knowledge = []
                            for kb in knowledge:
                                if isinstance(kb, dict):
                                    # Keep only essential knowledge base info
                                    cleaned_kb = {
                                        "id": kb.get("id"),
                                        "name": kb.get("name"),
                                        "collection_name": kb.get("collection_name"),
                                    }
                                    cleaned_knowledge.append(cleaned_kb)
                                else:
                                    cleaned_knowledge.append(kb)
                            cleaned_meta["knowledge"] = cleaned_knowledge
                    
                    model_dict = {
                        "id": model.id,
                        "user_id": model.user_id,
                        "base_model_id": model.base_model_id,
                        "name": model.name,
                        "meta": ModelMeta(**cleaned_meta),
                        "params": model.params,
                        "access_control": model.access_control,
                        "is_active": model.is_active,
                        "updated_at": model.updated_at,
                        "created_at": model.created_at,
                        "user": user.model_dump() if user else None,
                    }
                    result.append(ModelMetadataResponse.model_validate(model_dict))
            
            return result

    def get_models_metadata_by_user_id(
        self, user_id: str, permission: str = "write"
    ) -> list[ModelMetadataResponse]:
        """
        Get models accessible to a user with only metadata (no knowledge file data).
        Optimized for listing pages that don't need full model data.
        """
        with get_db() as db:
            # Step 1: Fetch user's group memberships once
            user_groups = Groups.get_groups_by_member_id(user_id)
            user_group_ids = [group.id for group in user_groups]
            
            # Step 2: Fetch user's models
            user_models = (
                db.query(Model)
                .filter(Model.base_model_id != None)
                .filter(Model.user_id == user_id)
                .all()
            )
            
            # Step 3: Process other models with access control
            other_models = (
                db.query(Model)
                .filter(Model.base_model_id != None)
                .filter(Model.user_id != user_id)
                .all()
            )
            
            filtered_other_models = []
            for model in other_models:
                if model.access_control is None:
                    if permission == "read":
                        filtered_other_models.append(model)
                    continue
                
                permission_access = model.access_control.get(permission, {})
                permitted_group_ids = permission_access.get("group_ids", [])
                permitted_user_ids = permission_access.get("user_ids", [])
                
                if (user_id in permitted_user_ids or 
                    any(g_id in permitted_group_ids for g_id in user_group_ids)):
                    filtered_other_models.append(model)
            
            all_models = user_models + filtered_other_models
            
            if not all_models:
                return []
            
            # Step 4: Get user data
            user_ids = {model.user_id for model in all_models if model.user_id}
            user_dict = {}
            if user_ids:
                users = Users.get_users_by_ids(list(user_ids))
                user_dict = {user.id: user for user in users}
            
            # Step 5: Build response with cleaned meta
            result = []
            batch_size = 50
            for i in range(0, len(all_models), batch_size):
                batch = all_models[i:i+batch_size]
                for model in batch:
                    user = user_dict.get(model.user_id)
                    
                    # Clean meta to remove knowledge file data
                    meta_dict = model.meta if model.meta else {}
                    cleaned_meta = {
                        "profile_image_url": meta_dict.get("profile_image_url", "/static/favicon.png"),
                        "description": meta_dict.get("description"),
                        "capabilities": meta_dict.get("capabilities"),
                    }
                    # Keep knowledge base references but not file data
                    if "knowledge" in meta_dict:
                        knowledge = meta_dict.get("knowledge", [])
                        if isinstance(knowledge, list):
                            cleaned_knowledge = []
                            for kb in knowledge:
                                if isinstance(kb, dict):
                                    cleaned_kb = {
                                        "id": kb.get("id"),
                                        "name": kb.get("name"),
                                        "collection_name": kb.get("collection_name"),
                                    }
                                    cleaned_knowledge.append(cleaned_kb)
                                else:
                                    cleaned_knowledge.append(kb)
                            cleaned_meta["knowledge"] = cleaned_knowledge
                    
                    model_dict = {
                        "id": model.id,
                        "user_id": model.user_id,
                        "base_model_id": model.base_model_id,
                        "name": model.name,
                        "meta": ModelMeta(**cleaned_meta),
                        "params": model.params,
                        "access_control": model.access_control,
                        "is_active": model.is_active,
                        "updated_at": model.updated_at,
                        "created_at": model.created_at,
                        "user": user.model_dump() if user else None,
                    }
                    result.append(ModelMetadataResponse.model_validate(model_dict))
            
            return result

    def get_model_by_id(self, id: str) -> Optional[ModelModel]:
        try:
            with get_db() as db:
                model = db.get(Model, id)
                return ModelModel.model_validate(model)
        except Exception:
            return None

    def toggle_model_by_id(self, id: str) -> Optional[ModelModel]:
        with get_db() as db:
            try:
                is_active = db.query(Model).filter_by(id=id).first().is_active

                db.query(Model).filter_by(id=id).update(
                    {
                        "is_active": not is_active,
                        "updated_at": int(time.time()),
                    }
                )
                db.commit()

                return self.get_model_by_id(id)
            except Exception:
                return None

    def update_model_by_id(self, id: str, model: ModelForm) -> Optional[ModelModel]:
        try:
            with get_db() as db:
                # update only the fields that are present in the model
                result = (
                    db.query(Model)
                    .filter_by(id=id)
                    .update(model.model_dump(exclude={"id"}))
                )
                db.commit()

                model = db.get(Model, id)
                db.refresh(model)
                return ModelModel.model_validate(model)
        except Exception as e:
            log.exception(f"Failed to update the model by id {id}: {e}")
            return None

    def delete_model_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                db.query(Model).filter_by(id=id).delete()
                db.commit()

                return True
        except Exception:
            return False

    def delete_all_models(self) -> bool:
        try:
            with get_db() as db:
                db.query(Model).delete()
                db.commit()

                return True
        except Exception:
            return False


Models = ModelsTable()
