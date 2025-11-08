from typing import Optional

from open_webui.models.models import (
    ModelForm,
    ModelModel,
    ModelResponse,
    ModelUserResponse,
    ModelMetadataResponse,
    Models,
)
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, Request, status


from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_access, has_permission
from open_webui.utils.model_images import get_or_create_model_image_file, convert_file_url_to_absolute


router = APIRouter()


###########################
# GetModels
###########################


@router.get("/", response_model=list[ModelUserResponse])
async def get_models(request: Request, id: Optional[str] = None, user=Depends(get_verified_user)):
    if user.role == "admin":
        models = Models.get_models()
    else:
        models = Models.get_models_by_user_id(user.id)
    
    # Convert relative file URLs to absolute URLs
    from open_webui.models.models import ModelMeta
    result = []
    for model in models:
        if model.meta and model.meta.profile_image_url:
            # Create new ModelMeta with absolute URL
            meta_dict = model.meta.model_dump()
            meta_dict["profile_image_url"] = convert_file_url_to_absolute(request, model.meta.profile_image_url)
            # Create new model instance with updated meta
            model_dict = model.model_dump()
            model_dict["meta"] = ModelMeta(**meta_dict)
            result.append(ModelUserResponse(**model_dict))
        else:
            result.append(model)
    
    return result


###########################
# GetModelsMetadata
###########################


@router.get("/metadata", response_model=list[ModelMetadataResponse])
async def get_models_metadata(request: Request, user=Depends(get_verified_user)):
    """
    Get workspace models with only metadata (no knowledge/RAG file data).
    Optimized for listing pages that don't need full model data.
    """
    if user.role == "admin":
        models = Models.get_models_metadata()
    else:
        models = Models.get_models_metadata_by_user_id(user.id)
    
    # Convert relative file URLs to absolute URLs
    from open_webui.models.models import ModelMeta
    result = []
    for model in models:
        if model.meta and model.meta.profile_image_url:
            # Create new ModelMeta with absolute URL
            meta_dict = model.meta.model_dump()
            meta_dict["profile_image_url"] = convert_file_url_to_absolute(request, model.meta.profile_image_url)
            # Create new model instance with updated meta
            model_dict = model.model_dump()
            model_dict["meta"] = ModelMeta(**meta_dict)
            result.append(ModelMetadataResponse(**model_dict))
        else:
            result.append(model)
    
    return result


###########################
# GetBaseModels
###########################


@router.get("/base", response_model=list[ModelResponse])
async def get_base_models(request: Request, user=Depends(get_admin_user)):
    models = Models.get_base_models()
    # Convert relative file URLs to absolute URLs
    from open_webui.models.models import ModelMeta
    result = []
    for model in models:
        if model.meta and model.meta.profile_image_url:
            # Create new ModelMeta with absolute URL
            meta_dict = model.meta.model_dump()
            meta_dict["profile_image_url"] = convert_file_url_to_absolute(request, model.meta.profile_image_url)
            # Create new model instance with updated meta
            model_dict = model.model_dump()
            model_dict["meta"] = ModelMeta(**meta_dict)
            result.append(ModelResponse(**model_dict))
        else:
            result.append(model)
    return result


############################
# CreateNewModel
############################


@router.post("/create", response_model=Optional[ModelModel])
async def create_new_model(
    request: Request,
    form_data: ModelForm,
    user=Depends(get_verified_user),
):
    if user.role != "admin" and not has_permission(
        user.id, "workspace.models", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    model = Models.get_model_by_id(form_data.id)
    if model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.MODEL_ID_TAKEN,
        )

    else:
        # Convert base64 image to filesystem storage if needed
        if form_data.meta and form_data.meta.profile_image_url:
            converted_url = get_or_create_model_image_file(
                request, user.id, form_data.meta.profile_image_url
            )
            form_data.meta.profile_image_url = converted_url
        
        # Ensure tags exist in database if meta.tags is present
        if form_data.meta:
            meta_dict = form_data.meta.model_dump()
            if "tags" in meta_dict and meta_dict["tags"]:
                from open_webui.models.tags import Tags
                Tags.ensure_tags_exist(meta_dict["tags"], user.id)
        
        model = Models.insert_new_model(form_data, user.id)
        if model:
            # Convert relative file URL to absolute URL
            if model.meta and model.meta.profile_image_url:
                from open_webui.models.models import ModelMeta
                meta_dict = model.meta.model_dump()
                meta_dict["profile_image_url"] = convert_file_url_to_absolute(request, model.meta.profile_image_url)
                model_dict = model.model_dump()
                model_dict["meta"] = ModelMeta(**meta_dict)
                return ModelModel(**model_dict)
            return model
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.DEFAULT(),
            )


###########################
# GetModelById
###########################


# Note: We're not using the typical url path param here, but instead using a query parameter to allow '/' in the id
@router.get("/model", response_model=Optional[ModelResponse])
async def get_model_by_id(request: Request, id: str, user=Depends(get_verified_user)):
    model = Models.get_model_by_id(id)
    if model:
        if (
            user.role == "admin"
            or model.user_id == user.id
            or has_access(user.id, "read", model.access_control)
        ):
            # Convert relative file URL to absolute URL
            if model.meta and model.meta.profile_image_url:
                from open_webui.models.models import ModelMeta
                meta_dict = model.meta.model_dump()
                meta_dict["profile_image_url"] = convert_file_url_to_absolute(request, model.meta.profile_image_url)
                model_dict = model.model_dump()
                model_dict["meta"] = ModelMeta(**meta_dict)
                return ModelResponse(**model_dict)
            return model
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# ToggelModelById
############################


@router.post("/model/toggle", response_model=Optional[ModelResponse])
async def toggle_model_by_id(request: Request, id: str, user=Depends(get_verified_user)):
    model = Models.get_model_by_id(id)
    if model:
        if (
            user.role == "admin"
            or model.user_id == user.id
            or has_access(user.id, "write", model.access_control)
        ):
            model = Models.toggle_model_by_id(id)

            if model:
                # Convert relative file URL to absolute URL
                if model.meta and model.meta.profile_image_url:
                    from open_webui.models.models import ModelMeta
                    meta_dict = model.meta.model_dump()
                    meta_dict["profile_image_url"] = convert_file_url_to_absolute(request, model.meta.profile_image_url)
                    model_dict = model.model_dump()
                    model_dict["meta"] = ModelMeta(**meta_dict)
                    return ModelResponse(**model_dict)
                return model
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT("Error updating function"),
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.UNAUTHORIZED,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# UpdateModelById
############################


@router.post("/model/update", response_model=Optional[ModelModel])
async def update_model_by_id(
    request: Request,
    id: str,
    form_data: ModelForm,
    user=Depends(get_verified_user),
):
    model = Models.get_model_by_id(id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        model.user_id != user.id
        and not has_access(user.id, "write", model.access_control)
        and user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    # Convert base64 image to filesystem storage if needed
    if form_data.meta and form_data.meta.profile_image_url:
        converted_url = get_or_create_model_image_file(
            request, user.id, form_data.meta.profile_image_url
        )
        form_data.meta.profile_image_url = converted_url

    # Ensure tags exist in database if meta.tags is present
    if form_data.meta:
        meta_dict = form_data.meta.model_dump()
        if "tags" in meta_dict and meta_dict["tags"]:
            from open_webui.models.tags import Tags
            Tags.ensure_tags_exist(meta_dict["tags"], user.id)

    model = Models.update_model_by_id(id, form_data)
    if model:
        # Convert relative file URL to absolute URL
        if model.meta and model.meta.profile_image_url:
            from open_webui.models.models import ModelMeta
            meta_dict = model.meta.model_dump()
            meta_dict["profile_image_url"] = convert_file_url_to_absolute(request, model.meta.profile_image_url)
            model_dict = model.model_dump()
            model_dict["meta"] = ModelMeta(**meta_dict)
            return ModelModel(**model_dict)
    return model


############################
# DeleteModelById
############################


@router.delete("/model/delete", response_model=bool)
async def delete_model_by_id(id: str, user=Depends(get_verified_user)):
    model = Models.get_model_by_id(id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (
        user.role != "admin"
        and model.user_id != user.id
        and not has_access(user.id, "write", model.access_control)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    result = Models.delete_model_by_id(id)
    return result


@router.delete("/delete/all", response_model=bool)
async def delete_all_models(user=Depends(get_admin_user)):
    result = Models.delete_all_models()
    return result
