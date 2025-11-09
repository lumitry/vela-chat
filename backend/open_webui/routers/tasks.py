from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import StreamingResponse

from pydantic import BaseModel
from typing import Optional
import logging
import re
import json

from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.task import (
    title_generation_template,
    query_generation_template,
    image_prompt_generation_template,
    autocomplete_generation_template,
    tags_generation_template,
    emoji_generation_template,
    moa_response_generation_template,
)
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.constants import TASKS

from open_webui.routers.pipelines import process_pipeline_inlet_filter
from open_webui.utils.filter import (
    get_sorted_filter_ids,
    process_filter_functions,
)
from open_webui.utils.task import get_task_model_id
from open_webui.services.task_metrics import record_task_generation

from open_webui.config import (
    DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE,
)
from open_webui.env import SRC_LOG_LEVELS


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


##################################
#
# Task Endpoints
#
##################################


@router.get("/config")
async def get_task_config(request: Request, user=Depends(get_verified_user)):
    return {
        "TASK_MODEL": request.app.state.config.TASK_MODEL,
        "TASK_MODEL_EXTERNAL": request.app.state.config.TASK_MODEL_EXTERNAL,
        "TITLE_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE,
        "IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE": request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_AUTOCOMPLETE_GENERATION": request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION,
        "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH": request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,
        "TAGS_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_TAGS_GENERATION": request.app.state.config.ENABLE_TAGS_GENERATION,
        "ENABLE_TITLE_GENERATION": request.app.state.config.ENABLE_TITLE_GENERATION,
        "ENABLE_SEARCH_QUERY_GENERATION": request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION,
        "ENABLE_RETRIEVAL_QUERY_GENERATION": request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION,
        "QUERY_GENERATION_PROMPT_TEMPLATE": request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE,
        "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE": request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    }


class TaskConfigForm(BaseModel):
    TASK_MODEL: Optional[str]
    TASK_MODEL_EXTERNAL: Optional[str]
    ENABLE_TITLE_GENERATION: bool
    TITLE_GENERATION_PROMPT_TEMPLATE: str
    IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_AUTOCOMPLETE_GENERATION: bool
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH: int
    TAGS_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_TAGS_GENERATION: bool
    ENABLE_SEARCH_QUERY_GENERATION: bool
    ENABLE_RETRIEVAL_QUERY_GENERATION: bool
    QUERY_GENERATION_PROMPT_TEMPLATE: str
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE: str


@router.post("/config/update")
async def update_task_config(
    request: Request, form_data: TaskConfigForm, user=Depends(get_admin_user)
):
    request.app.state.config.TASK_MODEL = form_data.TASK_MODEL
    request.app.state.config.TASK_MODEL_EXTERNAL = form_data.TASK_MODEL_EXTERNAL
    request.app.state.config.ENABLE_TITLE_GENERATION = form_data.ENABLE_TITLE_GENERATION
    request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE = (
        form_data.TITLE_GENERATION_PROMPT_TEMPLATE
    )

    request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = (
        form_data.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE
    )

    request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION = (
        form_data.ENABLE_AUTOCOMPLETE_GENERATION
    )
    request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH = (
        form_data.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH
    )

    request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE = (
        form_data.TAGS_GENERATION_PROMPT_TEMPLATE
    )
    request.app.state.config.ENABLE_TAGS_GENERATION = form_data.ENABLE_TAGS_GENERATION
    request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION = (
        form_data.ENABLE_SEARCH_QUERY_GENERATION
    )
    request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION = (
        form_data.ENABLE_RETRIEVAL_QUERY_GENERATION
    )

    request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE = (
        form_data.QUERY_GENERATION_PROMPT_TEMPLATE
    )
    request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = (
        form_data.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
    )

    return {
        "TASK_MODEL": request.app.state.config.TASK_MODEL,
        "TASK_MODEL_EXTERNAL": request.app.state.config.TASK_MODEL_EXTERNAL,
        "ENABLE_TITLE_GENERATION": request.app.state.config.ENABLE_TITLE_GENERATION,
        "TITLE_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE,
        "IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE": request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_AUTOCOMPLETE_GENERATION": request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION,
        "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH": request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,
        "TAGS_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_TAGS_GENERATION": request.app.state.config.ENABLE_TAGS_GENERATION,
        "ENABLE_SEARCH_QUERY_GENERATION": request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION,
        "ENABLE_RETRIEVAL_QUERY_GENERATION": request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION,
        "QUERY_GENERATION_PROMPT_TEMPLATE": request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE,
        "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE": request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    }


@router.post("/title/completions")
async def generate_title(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    if not request.app.state.config.ENABLE_TITLE_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Title generation is disabled"},
        )

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating chat title using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE

    messages = form_data["messages"]

    # Remove reasoning details from the messages
    for message in messages:
        message["content"] = re.sub(
            r"<details\s+type=\"reasoning\"[^>]*>.*?<\/details>",
            "",
            message["content"],
            flags=re.S,
        ).strip()

    content = title_generation_template(
        template,
        messages,
        {
            "name": user.name,
            "location": user.info.get("location") if user.info else None,
        },
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "usage": {"include": True},
        **(
            {"max_tokens": 1000}
            if models[task_model_id].get("owned_by") == "ollama"
            else {
                "max_completion_tokens": 1000,
            }
        ),
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.TITLE_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Record task generation
        if isinstance(response, dict):
            choices = response.get("choices", [])
            response_text = None
            if choices and len(choices) > 0:
                response_text = choices[0].get("message", {}).get("content", "")
            
            usage = response.get("usage")
            error = response.get("error")
            
            chat_id = form_data.get("chat_id")
            message_id = form_data.get("message_id")  # Will be passed from caller
            
            if chat_id and message_id:
                template_source = "config" if request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE != "" else "default"
                record_task_generation(
                    task_type=str(TASKS.TITLE_GENERATION),
                    chat_id=chat_id,
                    message_id=message_id,
                    user_id=user.id,
                    task_model_id=task_model_id,
                    models=models,
                    template_string=template,
                    template_source=template_source,
                    response_text=response_text,
                    usage=usage,
                    error=error,
                )
        
        return response
    except Exception as e:
        log.error("Exception occurred", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/tags/completions")
async def generate_chat_tags(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    if not request.app.state.config.ENABLE_TAGS_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Tags generation is disabled"},
        )

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating chat tags using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE

    content = tags_generation_template(
        template, form_data["messages"], {"name": user.name}
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "usage": {"include": True},
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.TAGS_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Record task generation
        if isinstance(response, dict):
            choices = response.get("choices", [])
            response_text = None
            if choices and len(choices) > 0:
                response_text = choices[0].get("message", {}).get("content", "")
            
            usage = response.get("usage")
            error = response.get("error")
            
            chat_id = form_data.get("chat_id")
            message_id = form_data.get("message_id")  # Will be passed from caller
            
            if chat_id and message_id:
                template_source = "config" if request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE != "" else "default"
                record_task_generation(
                    task_type=str(TASKS.TAGS_GENERATION),
                    chat_id=chat_id,
                    message_id=message_id,
                    user_id=user.id,
                    task_model_id=task_model_id,
                    models=models,
                    template_string=template,
                    template_source=template_source,
                    response_text=response_text,
                    usage=usage,
                    error=error,
                )
        
        return response
    except Exception as e:
        log.error(f"Error generating chat completion: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/image_prompt/completions")
async def generate_image_prompt(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating image prompt using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE

    content = image_prompt_generation_template(
        template,
        form_data["messages"],
        user={
            "name": user.name,
        },
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "usage": {"include": True},
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.IMAGE_PROMPT_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Record task generation
        if isinstance(response, dict):
            choices = response.get("choices", [])
            response_text = None
            if choices and len(choices) > 0:
                response_text = choices[0].get("message", {}).get("content", "")
            
            usage = response.get("usage")
            error = response.get("error")
            
            # Try to get chat_id and message_id from various sources
            chat_id = (
                form_data.get("chat_id") or
                (hasattr(request.state, "metadata") and request.state.metadata.get("chat_id")) or
                payload.get("metadata", {}).get("chat_id")
            )
            message_id = form_data.get("message_id")
            
            # If we have chat_id but not message_id, try to get it from the chat
            if chat_id and not message_id:
                try:
                    from open_webui.models.chat_messages import ChatMessages
                    all_messages = ChatMessages.get_all_messages_by_chat_id(chat_id)
                    user_messages = [m for m in all_messages if m.role == "user"]
                    if user_messages:
                        message_id = user_messages[-1].id
                except Exception as e:
                    log.debug(f"Could not get message_id for image prompt generation: {e}")
            
            if chat_id and message_id:
                template_source = "config" if request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE != "" else "default"
                record_task_generation(
                    task_type=str(TASKS.IMAGE_PROMPT_GENERATION),
                    chat_id=chat_id,
                    message_id=message_id,
                    user_id=user.id,
                    task_model_id=task_model_id,
                    models=models,
                    template_string=template,
                    template_source=template_source,
                    response_text=response_text,
                    usage=usage,
                    error=error,
                )
        
        return response
    except Exception as e:
        log.error("Exception occurred", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/queries/completions")
async def generate_queries(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    type = form_data.get("type")
    if type == "web_search":
        if not request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Search query generation is disabled",
            )
    elif type == "retrieval":
        if not request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Query generation is disabled",
            )

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating {type} queries using model {task_model_id} for user {user.email}"
    )

    if (request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE).strip() != "":
        template = request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE

    content = query_generation_template(
        template, form_data["messages"], {"name": user.name}
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "usage": {"include": True},
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.QUERY_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Record task generation
        if isinstance(response, dict):
            choices = response.get("choices", [])
            response_text = None
            if choices and len(choices) > 0:
                response_text = choices[0].get("message", {}).get("content", "")
            
            usage = response.get("usage")
            error = response.get("error")
            
            chat_id = form_data.get("chat_id")
            message_id = form_data.get("message_id")  # Will be passed from caller
            
            if chat_id and message_id:
                template_source = "config" if (request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE).strip() != "" else "default"
                record_task_generation(
                    task_type=str(TASKS.QUERY_GENERATION),
                    chat_id=chat_id,
                    message_id=message_id,
                    user_id=user.id,
                    task_model_id=task_model_id,
                    models=models,
                    template_string=template,
                    template_source=template_source,
                    response_text=response_text,
                    usage=usage,
                    error=error,
                )
        
        return response
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )


@router.post("/auto/completions")
async def generate_autocompletion(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    if not request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Autocompletion generation is disabled",
        )

    type = form_data.get("type")
    prompt = form_data.get("prompt")
    messages = form_data.get("messages")

    if request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH > 0:
        if (
            len(prompt)
            > request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Input prompt exceeds maximum length of {request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH}",
            )

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating autocompletion using model {task_model_id} for user {user.email}"
    )

    if (request.app.state.config.AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE).strip() != "":
        template = request.app.state.config.AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE

    content = autocomplete_generation_template(
        template, prompt, messages, type, {"name": user.name}
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "usage": {"include": True},
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.AUTOCOMPLETE_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Record task generation
        if isinstance(response, dict):
            choices = response.get("choices", [])
            response_text = None
            if choices and len(choices) > 0:
                response_text = choices[0].get("message", {}).get("content", "")
            
            usage = response.get("usage")
            error = response.get("error")
            
            # Try to get chat_id and message_id from various sources
            chat_id = (
                form_data.get("chat_id") or
                (hasattr(request.state, "metadata") and request.state.metadata.get("chat_id")) or
                payload.get("metadata", {}).get("chat_id")
            )
            message_id = form_data.get("message_id")
            
            # Try to extract chat_id from messages if available (messages might have metadata)
            if not chat_id and messages:
                try:
                    # Check if any message has chat_id in metadata
                    for msg in messages:
                        if isinstance(msg, dict) and msg.get("metadata", {}).get("chat_id"):
                            chat_id = msg["metadata"]["chat_id"]
                            break
                except Exception as e:
                    log.debug(f"Could not extract chat_id from messages: {e}")
            
            # If we have chat_id but not message_id, try to get it from the chat
            if chat_id and not message_id:
                try:
                    from open_webui.models.chat_messages import ChatMessages
                    all_messages = ChatMessages.get_all_messages_by_chat_id(chat_id)
                    user_messages = [m for m in all_messages if m.role == "user"]
                    if user_messages:
                        message_id = user_messages[-1].id
                except Exception as e:
                    log.debug(f"Could not get message_id for autocomplete generation: {e}")
            
            # Log for debugging
            if not chat_id:
                log.debug(f"Autocomplete generation: No chat_id found. form_data keys: {list(form_data.keys())}, has request.state.metadata: {hasattr(request.state, 'metadata')}")
            elif not message_id:
                log.debug(f"Autocomplete generation: chat_id={chat_id} but no message_id found")
            
            if chat_id and message_id:
                template_source = "config" if (request.app.state.config.AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE).strip() != "" else "default"
                record_task_generation(
                    task_type=str(TASKS.AUTOCOMPLETE_GENERATION),
                    chat_id=chat_id,
                    message_id=message_id,
                    user_id=user.id,
                    task_model_id=task_model_id,
                    models=models,
                    template_string=template,
                    template_source=template_source,
                    response_text=response_text,
                    usage=usage,
                    error=error,
                )
            else:
                log.warning(f"Autocomplete generation not recorded: chat_id={chat_id}, message_id={message_id}")
        
        return response
    except Exception as e:
        log.error(f"Error generating chat completion: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/emoji/completions")
async def generate_emoji(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(f"generating emoji using model {task_model_id} for user {user.email} ")

    template = DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE

    content = emoji_generation_template(
        template,
        form_data["prompt"],
        {
            "name": user.name,
            "location": user.info.get("location") if user.info else None,
        },
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "usage": {"include": True},
        **(
            {"max_tokens": 4}
            if models[task_model_id].get("owned_by") == "ollama"
            else {
                "max_completion_tokens": 4,
            }
        ),
        "chat_id": form_data.get("chat_id", None),
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.EMOJI_GENERATION),
            "task_body": form_data,
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Record task generation
        if isinstance(response, dict):
            choices = response.get("choices", [])
            response_text = None
            if choices and len(choices) > 0:
                response_text = choices[0].get("message", {}).get("content", "")
            
            usage = response.get("usage")
            error = response.get("error")
            
            chat_id = form_data.get("chat_id")
            message_id = form_data.get("message_id")  # Will be passed from caller
            
            if chat_id and message_id:
                # Emoji generation always uses default template
                record_task_generation(
                    task_type=str(TASKS.EMOJI_GENERATION),
                    chat_id=chat_id,
                    message_id=message_id,
                    user_id=user.id,
                    task_model_id=task_model_id,
                    models=models,
                    template_string=template,
                    template_source="default",
                    response_text=response_text,
                    usage=usage,
                    error=error,
                )
        
        return response
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )


@router.post("/moa/completions")
async def generate_moa_response(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]

    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    template = DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE

    content = moa_response_generation_template(
        template,
        form_data["prompt"],
        form_data["responses"],
    )

    stream = form_data.get("stream", False)
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": stream,
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "chat_id": form_data.get("chat_id", None),
            "task": str(TASKS.MOA_RESPONSE_GENERATION),
            "task_body": form_data,
        },
    }
    
    # Include usage for both streaming and non-streaming requests
    if stream:
        payload["stream_options"] = {"include_usage": True}
    else:
        payload["usage"] = {"include": True}

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Try to get chat_id and message_id from various sources (needed for both streaming and non-streaming)
        chat_id = (
            form_data.get("chat_id") or
            (hasattr(request.state, "metadata") and request.state.metadata.get("chat_id")) or
            payload.get("metadata", {}).get("chat_id")
        )
        message_id = (
            form_data.get("message_id") or
            (hasattr(request.state, "metadata") and request.state.metadata.get("message_id")) or
            payload.get("metadata", {}).get("message_id")
        )
        
        # Log for debugging
        if not chat_id:
            log.debug(f"MOA generation: No chat_id found. form_data keys: {list(form_data.keys())}, has request.state.metadata: {hasattr(request.state, 'metadata')}")
        elif not message_id:
            log.debug(f"MOA generation: chat_id={chat_id} but no message_id found")
        
        # If we have chat_id but not message_id, try to get it from the chat
        if chat_id and not message_id:
            try:
                from open_webui.models.chat_messages import ChatMessages
                all_messages = ChatMessages.get_all_messages_by_chat_id(chat_id)
                # For MOA, we want the assistant message that triggered the merge
                # This would be the most recent assistant message
                assistant_messages = [m for m in all_messages if m.role == "assistant"]
                if assistant_messages:
                    message_id = assistant_messages[-1].id
            except Exception as e:
                log.debug(f"Could not get message_id for MOA generation: {e}")
        
        if not chat_id or not message_id:
            log.warning(f"MOA generation not recorded: chat_id={chat_id}, message_id={message_id}")
        
        # Handle streaming response
        if isinstance(response, StreamingResponse) and stream:
            # Wrap the streaming response to intercept usage data
            async def stream_with_usage_tracking():
                nonlocal chat_id, message_id
                response_text = ""
                usage_data = None
                error_data = None
                
                async for chunk in response.body_iterator:
                    # Yield the chunk as-is
                    yield chunk
                    
                    # Try to extract usage from the chunk
                    try:
                        # Convert chunk to string
                        if isinstance(chunk, bytes):
                            chunk_str = chunk.decode("utf-8")
                        elif isinstance(chunk, (bytearray, memoryview)):
                            chunk_str = bytes(chunk).decode("utf-8")
                        else:
                            chunk_str = str(chunk)
                        
                        # Look for SSE format: "data: {...}"
                        for line in chunk_str.split("\n"):
                            line = line.strip()
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if data_str and data_str != "[DONE]":
                                    try:
                                        data = json.loads(data_str)
                                        # Extract usage if present (can be in same chunk as choices)
                                        if "usage" in data:
                                            usage_data = data.get("usage")
                                            log.debug(f"MOA streaming: Found usage data: {usage_data}")
                                        # Extract error if present
                                        if "error" in data:
                                            error_data = data.get("error")
                                        # Extract content from choices
                                        choices = data.get("choices", [])
                                        if choices and len(choices) > 0:
                                            delta = choices[0].get("delta", {})
                                            content = delta.get("content", "")
                                            if content:
                                                response_text += content
                                    except json.JSONDecodeError:
                                        pass
                    except Exception as e:
                        log.debug(f"Error parsing streaming chunk: {e}")
                
                # Record task generation after stream completes
                if chat_id and message_id:
                    # MOA generation always uses default template
                    # Ensure message_id is a string
                    message_id_str = str(message_id) if message_id else None
                    if message_id_str:
                        log.debug(f"MOA streaming: Recording task generation with usage: {usage_data}")
                        record_task_generation(
                            task_type=str(TASKS.MOA_RESPONSE_GENERATION),
                            chat_id=str(chat_id),
                            message_id=message_id_str,
                            user_id=user.id,
                            task_model_id=model_id,  # MOA uses the main model, not task model
                            models=models,
                            template_string=template,
                            template_source="default",
                            response_text=response_text if response_text else None,
                            usage=usage_data,
                            error=error_data,
                        )
                        # Store merged content in message meta
                        if response_text:
                            try:
                                from open_webui.models.chat_messages import ChatMessages
                                ChatMessages.set_merged_metadata(
                                    message_id_str,
                                    response_text,
                                    merged_status=True
                                )
                                log.debug(f"MOA streaming: Stored merged content in message meta ({len(response_text)} chars)")
                            except Exception as e:
                                log.warning(f"MOA streaming: Failed to store merged metadata: {e}")
                else:
                    log.warning(f"MOA streaming: Cannot record - chat_id={chat_id}, message_id={message_id}, usage_data={usage_data}")
            
            return StreamingResponse(
                stream_with_usage_tracking(),
                media_type=response.media_type,
                headers=dict(response.headers),
            )
        
        # Handle non-streaming response
        elif isinstance(response, dict) and not stream:
            choices = response.get("choices", [])
            response_text = None
            if choices and len(choices) > 0:
                response_text = choices[0].get("message", {}).get("content", "")
            
            usage = response.get("usage")
            error = response.get("error")
            
            if chat_id and message_id:
                # MOA generation always uses default template
                # Ensure message_id is a string
                message_id_str = str(message_id) if message_id else None
                if message_id_str:
                    record_task_generation(
                        task_type=str(TASKS.MOA_RESPONSE_GENERATION),
                        chat_id=str(chat_id),
                        message_id=message_id_str,
                        user_id=user.id,
                        task_model_id=model_id,  # MOA uses the main model, not task model
                        models=models,
                        template_string=template,
                        template_source="default",
                        response_text=response_text,
                        usage=usage,
                        error=error,
                    )
                    # Store merged content in message meta
                    if response_text:
                        try:
                            from open_webui.models.chat_messages import ChatMessages
                            ChatMessages.set_merged_metadata(
                                message_id_str,
                                response_text,
                                merged_status=True
                            )
                            log.debug(f"MOA non-streaming: Stored merged content in message meta ({len(response_text)} chars)")
                        except Exception as e:
                            log.warning(f"MOA non-streaming: Failed to store merged metadata: {e}")
        
        return response
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )
