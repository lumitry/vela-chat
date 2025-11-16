import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
import mimetypes


from open_webui.models.folders import (
    FolderForm,
    FolderModel,
    Folders,
)
from open_webui.models.chats import Chats

from open_webui.config import UPLOAD_DIR
from open_webui.env import SRC_LOG_LEVELS
from open_webui.constants import ERROR_MESSAGES


from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Request
from fastapi.responses import FileResponse, StreamingResponse


from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_permission


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


router = APIRouter()


############################
# Get Folders
############################


@router.get("/", response_model=list[FolderModel])
async def get_folders(user=Depends(get_verified_user)):
    folders = Folders.get_folders_by_user_id(user.id)
    
    # If there are no folders, return early
    if not folders:
        return []
    
    # Get all folder IDs
    folder_ids = [folder.id for folder in folders]
    
    # Fetch all chats for all folders in a single query
    folder_chats = Chats.get_all_folder_chats_by_user_id(user.id, folder_ids)
    
    # Build the response
    result = []
    for folder in folders:
        folder_chat_items = folder_chats.get(folder.id, [])
        result.append({
            **folder.model_dump(),
            "items": {
                "chats": folder_chat_items
            },
        })
    
    return result


############################
# Create Folder
############################


@router.post("/")
def create_folder(form_data: FolderForm, user=Depends(get_verified_user)):
    folder = Folders.get_folder_by_parent_id_and_user_id_and_name(
        form_data.parent_id, user.id, form_data.name
    )

    if folder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Folder already exists"),
        )

    try:
        folder = Folders.insert_new_folder(user.id, form_data.name, form_data.parent_id)
        return folder
    except Exception as e:
        log.exception(e)
        log.error("Error creating folder")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error creating folder"),
        )


############################
# Get Folders By Id
############################


@router.get("/{id}", response_model=Optional[FolderModel])
async def get_folder_by_id(id: str, user=Depends(get_verified_user)):
    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if folder:
        return folder
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# Update Folder Name By Id
############################


@router.post("/{id}/update")
async def update_folder_name_by_id(
    id: str, form_data: FolderForm, user=Depends(get_verified_user)
):
    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if folder:
        existing_folder = Folders.get_folder_by_parent_id_and_user_id_and_name(
            folder.parent_id, user.id, form_data.name
        )
        if existing_folder:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Folder already exists"),
            )

        try:
            folder = Folders.update_folder_name_by_id_and_user_id(
                id, user.id, form_data.name
            )

            return folder
        except Exception as e:
            log.exception(e)
            log.error(f"Error updating folder: {id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error updating folder"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# Update Folder Parent Id By Id
############################


class FolderParentIdForm(BaseModel):
    parent_id: Optional[str] = None


@router.post("/{id}/update/parent")
async def update_folder_parent_id_by_id(
    id: str, form_data: FolderParentIdForm, user=Depends(get_verified_user)
):
    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if folder:
        existing_folder = Folders.get_folder_by_parent_id_and_user_id_and_name(
            form_data.parent_id, user.id, folder.name
        )

        if existing_folder:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Folder already exists"),
            )

        try:
            folder = Folders.update_folder_parent_id_by_id_and_user_id(
                id, user.id, form_data.parent_id
            )
            return folder
        except Exception as e:
            log.exception(e)
            log.error(f"Error updating folder: {id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error updating folder"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

############################
# Batch Update Folder Is Expanded
# this one has to be up here to avoid 422 unprocessable entity error. no clue why, it just does.
############################


class FolderExpandedUpdate(BaseModel):
    id: str
    is_expanded: bool


class BatchFolderExpandedForm(BaseModel):
    updates: list[FolderExpandedUpdate]


@router.post("/batch/update/expanded")
async def batch_update_folder_is_expanded(
    form_data: BatchFolderExpandedForm, user=Depends(get_verified_user)
):
    """
    Batch update folder expanded states. More efficient than individual calls.
    """
    import time
    start_time = time.time()
    
    results = []
    errors = []
    
    for update in form_data.updates:
        try:
            folder = Folders.get_folder_by_id_and_user_id(update.id, user.id)
            if folder:
                updated_folder = Folders.update_folder_is_expanded_by_id_and_user_id(
                    update.id, user.id, update.is_expanded
                )
                if updated_folder:
                    results.append(updated_folder)
                else:
                    errors.append({"id": update.id, "error": "Failed to update"})
            else:
                errors.append({"id": update.id, "error": "Folder not found"})
        except Exception as e:
            log.exception(f"Error updating folder {update.id}: {e}")
            errors.append({"id": update.id, "error": str(e)})
    
    total_time = time.time()
    log.debug(f"[PERF] batch_update_folder_is_expanded: took {(total_time - start_time) * 1000:.2f}ms for {len(form_data.updates)} folders")
    
    return {
        "updated": results,
        "errors": errors,
        "success_count": len(results),
        "error_count": len(errors),
    }

############################
# Update Folder Is Expanded By Id
############################


class FolderIsExpandedForm(BaseModel):
    is_expanded: bool


@router.post("/{id}/update/expanded")
async def update_folder_is_expanded_by_id(
    id: str, form_data: FolderIsExpandedForm, user=Depends(get_verified_user)
):
    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if folder:
        try:
            folder = Folders.update_folder_is_expanded_by_id_and_user_id(
                id, user.id, form_data.is_expanded
            )
            return folder
        except Exception as e:
            log.exception(e)
            log.error(f"Error updating folder: {id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error updating folder"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# Delete Folder By Id
############################


@router.delete("/{id}")
async def delete_folder_by_id(
    request: Request, id: str, user=Depends(get_verified_user)
):
    chat_delete_permission = has_permission(
        user.id, "chat.delete", request.app.state.config.USER_PERMISSIONS
    )

    if user.role != "admin" and not chat_delete_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if folder:
        try:
            result = Folders.delete_folder_by_id_and_user_id(id, user.id)
            if result:
                return result
            else:
                raise Exception("Error deleting folder")
        except Exception as e:
            log.exception(e)
            log.error(f"Error deleting folder: {id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error deleting folder"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
