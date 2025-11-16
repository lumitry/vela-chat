import time
import logging
import sys

from aiocache import cached
from fastapi import Request

from open_webui.routers import openai, ollama
from open_webui.functions import get_function_models


from open_webui.models.functions import Functions
from open_webui.models.models import Models


from open_webui.utils.plugin import load_function_module_by_id
from open_webui.utils.access_control import has_access


from open_webui.config import (
    DEFAULT_ARENA_MODEL,
)

from open_webui.env import SRC_LOG_LEVELS, GLOBAL_LOG_LEVEL
from open_webui.models.users import UserModel


logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


async def get_all_base_models(request: Request, user: UserModel = None):
    import asyncio
    function_models = []
    openai_models = []
    ollama_models = []

    start_time = time.time()
    
    # Run OpenAI and Ollama model fetching in parallel
    async def fetch_openai_models():
        if request.app.state.config.ENABLE_OPENAI_API:
            models = await openai.get_all_models(request, user=user)
            return models.get("data", [])
        return []
    
    async def fetch_ollama_models():
        if request.app.state.config.ENABLE_OLLAMA_API:
            models_response = await ollama.get_all_models(request, user=user)
            # ollama.get_all_models returns a dict with "models" key
            if isinstance(models_response, dict) and "models" in models_response:
                return [
                    {
                        "id": model["model"],
                        "name": model["name"],
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "ollama",
                        "ollama": model,
                        "tags": model.get("tags", []),
                    }
                    for model in models_response.get("models", [])
                ]
        return []
    
    # Fetch models in parallel
    openai_task = fetch_openai_models()
    ollama_task = fetch_ollama_models()
    function_task = get_function_models(request)
    
    results = await asyncio.gather(
        openai_task,
        ollama_task,
        function_task,
        return_exceptions=True
    )
    
    # Handle exceptions and ensure we have lists
    openai_result, ollama_result, function_result = results
    
    if isinstance(openai_result, Exception):
        log.exception(f"Error fetching OpenAI models: {openai_result}")
        openai_models = []
    else:
        openai_models = openai_result if isinstance(openai_result, list) else []
    
    if isinstance(ollama_result, Exception):
        log.exception(f"Error fetching Ollama models: {ollama_result}")
        ollama_models = []
    else:
        ollama_models = ollama_result if isinstance(ollama_result, list) else []
    
    if isinstance(function_result, Exception):
        log.exception(f"Error fetching function models: {function_result}")
        function_models = []
    else:
        function_models = function_result if isinstance(function_result, list) else []
    
    t0 = time.time()
    log.debug(f"[PERF] get_all_models: parallel fetch took {(t0 - start_time) * 1000:.2f}ms")
    
    models = function_models + openai_models + ollama_models
    return models


async def get_all_models(request, user: UserModel = None):
    import time
    start_time = time.time()
    models = await get_all_base_models(request, user=user)
    end_time = time.time()
    log.debug(f"[PERF] get_all_models: get_all_base_models took {(end_time - start_time) * 1000:.2f}ms")

    # If there are no models, return an empty list
    if len(models) == 0:
        return []

    # Add arena models
    if request.app.state.config.ENABLE_EVALUATION_ARENA_MODELS:
        from open_webui.utils.model_images import convert_file_url_to_absolute
        
        arena_models = []
        if len(request.app.state.config.EVALUATION_ARENA_MODELS) > 0:
            arena_models = []
            for model in request.app.state.config.EVALUATION_ARENA_MODELS:
                model_dict = {
                    "id": model["id"],
                    "name": model["name"],
                    "info": {
                        "meta": model["meta"],
                    },
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "arena",
                    "arena": True,
                }
                # Convert relative file URLs to absolute URLs for arena model images
                if model_dict["info"]["meta"].get("profile_image_url"):
                    model_dict["info"]["meta"]["profile_image_url"] = convert_file_url_to_absolute(
                        request, model_dict["info"]["meta"]["profile_image_url"]
                    )
                arena_models.append(model_dict)
        else:
            # Add default arena model
            default_model = {
                "id": DEFAULT_ARENA_MODEL["id"],
                "name": DEFAULT_ARENA_MODEL["name"],
                "info": {
                    "meta": DEFAULT_ARENA_MODEL["meta"],
                },
                "object": "model",
                "created": int(time.time()),
                "owned_by": "arena",
                "arena": True,
            }
            # Convert relative file URLs to absolute URLs for default arena model image
            if default_model["info"]["meta"].get("profile_image_url"):
                default_model["info"]["meta"]["profile_image_url"] = convert_file_url_to_absolute(
                    request, default_model["info"]["meta"]["profile_image_url"]
                )
            arena_models = [default_model]
        models = models + arena_models

    global_action_ids = [
        function.id for function in Functions.get_global_action_functions()
    ]
    enabled_action_ids = [
        function.id
        for function in Functions.get_functions_by_type("action", active_only=True)
    ]

    custom_models = Models.get_all_models()
    for custom_model in custom_models:
        if custom_model.base_model_id is None:
            for model in models:
                if custom_model.id == model["id"] or (
                    model.get("owned_by") == "ollama"
                    and custom_model.id
                    == model["id"].split(":")[
                        0
                    ]  # Ollama may return model ids in different formats (e.g., 'llama3' vs. 'llama3:7b')
                ):
                    if custom_model.is_active:
                        model["name"] = custom_model.name
                        model_info_dict = custom_model.model_dump()
                        # Convert relative file URLs to absolute URLs
                        if "meta" in model_info_dict and model_info_dict["meta"].get("profile_image_url"):
                            from open_webui.utils.model_images import convert_file_url_to_absolute
                            model_info_dict["meta"]["profile_image_url"] = convert_file_url_to_absolute(
                                request, model_info_dict["meta"]["profile_image_url"]
                            )
                        model["info"] = model_info_dict

                        action_ids = []
                        if "info" in model and "meta" in model["info"]:
                            action_ids.extend(
                                model["info"]["meta"].get("actionIds", [])
                            )

                        model["action_ids"] = action_ids
                    else:
                        models.remove(model)

        elif custom_model.is_active and (
            custom_model.id not in [model["id"] for model in models]
        ):
            owned_by = "openai"
            pipe = None
            action_ids = []

            for model in models:
                if (
                    custom_model.base_model_id == model["id"]
                    or custom_model.base_model_id == model["id"].split(":")[0]
                ):
                    owned_by = model.get("owned_by", "unknown owner")
                    if "pipe" in model:
                        pipe = model["pipe"]
                    break

            if custom_model.meta:
                meta = custom_model.meta.model_dump()
                # Convert relative file URLs to absolute URLs
                if meta.get("profile_image_url"):
                    from open_webui.utils.model_images import convert_file_url_to_absolute
                    meta["profile_image_url"] = convert_file_url_to_absolute(
                        request, meta["profile_image_url"]
                    )
                if "actionIds" in meta:
                    action_ids.extend(meta["actionIds"])

            # Build info dict with converted URLs
            info_dict = custom_model.model_dump()
            if "meta" in info_dict and info_dict["meta"].get("profile_image_url"):
                from open_webui.utils.model_images import convert_file_url_to_absolute
                info_dict["meta"]["profile_image_url"] = convert_file_url_to_absolute(
                    request, info_dict["meta"]["profile_image_url"]
                )
            
            models.append(
                {
                    "id": f"{custom_model.id}",
                    "name": custom_model.name,
                    "object": "model",
                    "created": custom_model.created_at,
                    "owned_by": owned_by,
                    "info": info_dict,
                    "preset": True,
                    **({"pipe": pipe} if pipe is not None else {}),
                    "action_ids": action_ids,
                }
            )

    # Process action_ids to get the actions
    def get_action_items_from_module(function, module):
        actions = []
        if hasattr(module, "actions"):
            actions = module.actions
            return [
                {
                    "id": f"{function.id}.{action['id']}",
                    "name": action.get("name", f"{function.name} ({action['id']})"),
                    "description": function.meta.description,
                    "icon_url": action.get(
                        "icon_url", function.meta.manifest.get("icon_url", None)
                    ),
                }
                for action in actions
            ]
        else:
            return [
                {
                    "id": function.id,
                    "name": function.name,
                    "description": function.meta.description,
                    "icon_url": function.meta.manifest.get("icon_url", None),
                }
            ]

    def get_function_module_by_id(function_id):
        if function_id in request.app.state.FUNCTIONS:
            function_module = request.app.state.FUNCTIONS[function_id]
        else:
            function_module, _, _ = load_function_module_by_id(function_id)
            request.app.state.FUNCTIONS[function_id] = function_module

    # Batch fetch all action functions to avoid N+1 queries
    all_action_ids = set(global_action_ids)
    model_action_ids_map = {}  # Store action_ids per model before popping
    
    for idx, model in enumerate(models):
        model_action_ids = model.get("action_ids", [])
        all_action_ids.update(model_action_ids)
        model_action_ids_map[idx] = model_action_ids
        # Pop action_ids to prepare for processing
        model.pop("action_ids", None)
    
    # Filter to only enabled actions
    all_action_ids = [aid for aid in all_action_ids if aid in enabled_action_ids]
    
    # Batch fetch all action functions
    action_functions_map = {}
    for action_id in all_action_ids:
        action_function = Functions.get_function_by_id(action_id)
        if action_function is not None:
            action_functions_map[action_id] = action_function

    # Process actions for each model
    for idx, model in enumerate(models):
        model_action_ids = model_action_ids_map.get(idx, [])
        action_ids = [
            action_id
            for action_id in list(set(model_action_ids + global_action_ids))
            if action_id in enabled_action_ids
        ]

        model["actions"] = []
        for action_id in action_ids:
            action_function = action_functions_map.get(action_id)
            if action_function is None:
                log.warning(f"Action not found: {action_id}")
                continue

            function_module = get_function_module_by_id(action_id)
            model["actions"].extend(
                get_action_items_from_module(action_function, function_module)
            )
    log.debug(f"get_all_models() returned {len(models)} models")

    request.app.state.MODELS = {model["id"]: model for model in models}
    return models


def check_model_access(user, model):
    if model.get("arena"):
        if not has_access(
            user.id,
            type="read",
            access_control=model.get("info", {})
            .get("meta", {})
            .get("access_control", {}),
        ):
            raise Exception("Model not found")
    else:
        model_info = Models.get_model_by_id(model.get("id"))
        if not model_info:
            raise Exception("Model not found")
        elif not (
            user.id == model_info.user_id
            or has_access(
                user.id, type="read", access_control=model_info.access_control
            )
        ):
            raise Exception("Model not found")
