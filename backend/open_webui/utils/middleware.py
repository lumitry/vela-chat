import time
import logging
import sys
import os
import base64

import asyncio
from aiocache import cached
from typing import Any, Optional
import random
import json
import html
import inspect
import re
import ast

from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy


from fastapi import Request, HTTPException
from starlette.responses import Response, StreamingResponse


from open_webui.models.chats import Chats
from open_webui.models.users import Users
from open_webui.models.files import Files
from open_webui.models.chat_messages import ChatMessages, MessageCreateForm
from open_webui.storage.provider import Storage
from open_webui.socket.main import (
    get_event_call,
    get_event_emitter,
    get_active_status_by_user_id,
)
from open_webui.routers.tasks import (
    generate_queries,
    generate_title,
    generate_image_prompt,
    generate_chat_tags,
)
from open_webui.routers.retrieval import process_web_search, SearchForm
from open_webui.routers.images import image_generations, GenerateImageForm
from open_webui.routers.pipelines import (
    process_pipeline_inlet_filter,
    process_pipeline_outlet_filter,
)

from open_webui.utils.webhook import post_webhook


from open_webui.models.users import UserModel
from open_webui.models.functions import Functions
from open_webui.models.models import Models

from open_webui.retrieval.utils import get_sources_from_files


from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.task import (
    get_task_model_id,
    rag_template,
    tools_function_calling_generation_template,
)
from open_webui.utils.misc import (
    deep_update,
    get_message_list,
    add_or_update_system_message,
    add_or_update_user_message,
    get_last_user_message,
    get_last_user_message_item,
    get_last_assistant_message,
    prepend_to_first_user_message_content,
    convert_logit_bias_input_to_json,
)
from open_webui.utils.tools import get_tools
from open_webui.utils.plugin import load_function_module_by_id
from open_webui.utils.filter import (
    get_sorted_filter_ids,
    process_filter_functions,
)
from open_webui.utils.code_interpreter import execute_code_jupyter

from open_webui.tasks import create_task

from open_webui.config import (
    CACHE_DIR,
    DEFAULT_TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    DEFAULT_CODE_INTERPRETER_PROMPT,
)
from open_webui.env import (
    SRC_LOG_LEVELS,
    GLOBAL_LOG_LEVEL,
    BYPASS_MODEL_ACCESS_CONTROL,
    ENABLE_REALTIME_CHAT_SAVE,
)
from open_webui.constants import TASKS


logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


async def chat_completion_tools_handler(
    request: Request, body: dict, extra_params: dict, user: UserModel, models, tools
) -> tuple[dict, dict]:
    async def get_content_from_response(response) -> Optional[str]:
        content = None
        if hasattr(response, "body_iterator"):
            async for chunk in response.body_iterator:
                data = json.loads(chunk.decode("utf-8"))
                content = data["choices"][0]["message"]["content"]

            # Cleanup any remaining background tasks if necessary
            if response.background is not None:
                await response.background()
        else:
            content = response["choices"][0]["message"]["content"]
        return content

    def get_tools_function_calling_payload(messages, task_model_id, content):
        user_message = get_last_user_message(messages)
        history = "\n".join(
            f"{message['role'].upper()}: \"\"\"{message['content']}\"\"\""
            for message in messages[::-1][:4]
        )

        prompt = f"History:\n{history}\nQuery: {user_message}"

        return {
            "model": task_model_id,
            "messages": [
                {"role": "system", "content": content},
                {"role": "user", "content": f"Query: {prompt}"},
            ],
            "stream": False,
            "metadata": {"task": str(TASKS.FUNCTION_CALLING)},
        }

    event_caller = extra_params["__event_call__"]
    metadata = extra_params["__metadata__"]

    task_model_id = get_task_model_id(
        body["model"],
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    skip_files = False
    sources = []

    specs = [tool["spec"] for tool in tools.values()]
    tools_specs = json.dumps(specs)

    if request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE != "":
        template = request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE

    tools_function_calling_prompt = tools_function_calling_generation_template(
        template, tools_specs
    )
    payload = get_tools_function_calling_payload(
        body["messages"], task_model_id, tools_function_calling_prompt
    )

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        log.debug(f"{response=}")
        content = await get_content_from_response(response)
        log.debug(f"{content=}")

        if not content:
            return body, {}

        try:
            content = content[content.find("{") : content.rfind("}") + 1]
            if not content:
                raise Exception("No JSON object found in the response")

            result = json.loads(content)

            async def tool_call_handler(tool_call):
                nonlocal skip_files

                log.debug(f"{tool_call=}")

                tool_function_name = tool_call.get("name", None)
                if tool_function_name not in tools:
                    return body, {}

                tool_function_params = tool_call.get("parameters", {})

                try:
                    tool = tools[tool_function_name]

                    spec = tool.get("spec", {})
                    allowed_params = (
                        spec.get("parameters", {}).get("properties", {}).keys()
                    )
                    tool_function_params = {
                        k: v
                        for k, v in tool_function_params.items()
                        if k in allowed_params
                    }

                    if tool.get("direct", False):
                        tool_result = await event_caller(
                            {
                                "type": "execute:tool",
                                "data": {
                                    "id": str(uuid4()),
                                    "name": tool_function_name,
                                    "params": tool_function_params,
                                    "server": tool.get("server", {}),
                                    "session_id": metadata.get("session_id", None),
                                },
                            }
                        )
                    else:
                        tool_function = tool["callable"]
                        tool_result = await tool_function(**tool_function_params)

                except Exception as e:
                    tool_result = str(e)

                tool_result_files = []
                if isinstance(tool_result, list):
                    for item in tool_result:
                        # check if string
                        if isinstance(item, str) and item.startswith("data:"):
                            tool_result_files.append(item)
                            tool_result.remove(item)

                if isinstance(tool_result, dict) or isinstance(tool_result, list):
                    tool_result = json.dumps(tool_result, indent=2)

                if isinstance(tool_result, str):
                    tool = tools[tool_function_name]
                    tool_id = tool.get("tool_id", "")

                    tool_name = (
                        f"{tool_id}/{tool_function_name}"
                        if tool_id
                        else f"{tool_function_name}"
                    )
                    if tool.get("metadata", {}).get("citation", False) or tool.get(
                        "direct", False
                    ):
                        # Citation is enabled for this tool
                        sources.append(
                            {
                                "source": {
                                    "name": (f"TOOL:{tool_name}"),
                                },
                                "document": [tool_result],
                                "metadata": [{"source": (f"TOOL:{tool_name}")}],
                            }
                        )
                    else:
                        # Citation is not enabled for this tool
                        body["messages"] = add_or_update_user_message(
                            f"\nTool `{tool_name}` Output: {tool_result}",
                            body["messages"],
                        )

                    if (
                        tools[tool_function_name]
                        .get("metadata", {})
                        .get("file_handler", False)
                    ):
                        skip_files = True

            # check if "tool_calls" in result
            if result.get("tool_calls"):
                for tool_call in result.get("tool_calls"):
                    await tool_call_handler(tool_call)
            else:
                await tool_call_handler(result)

        except Exception as e:
            log.debug(f"Error: {e}")
            content = None
    except Exception as e:
        log.debug(f"Error: {e}")
        content = None

    log.debug(f"tool_contexts: {sources}")

    if skip_files and "files" in body.get("metadata", {}):
        del body["metadata"]["files"]

    return body, {"sources": sources}


async def chat_web_search_handler(
    request: Request, form_data: dict, extra_params: dict, user
):
    handler_start = time.perf_counter()
    event_emitter = extra_params["__event_emitter__"]
    await event_emitter(
        {
            "type": "status",
            "data": {
                "action": "web_search",
                "description": "Generating search query",
                "done": False,
            },
        }
    )

    messages = form_data["messages"]
    user_message = get_last_user_message(messages)

    # Try to get message_id for query generation tracking
    # For queries, we want the most recent user message ID
    message_id = None
    chat_id = form_data.get("chat_id") or extra_params.get("__metadata__", {}).get("chat_id")
    if chat_id:
        try:
            # Get the last user message from the chat
            all_messages = ChatMessages.get_all_messages_by_chat_id(chat_id)
            user_messages = [m for m in all_messages if m.role == "user"]
            if user_messages:
                message_id = user_messages[-1].id
        except Exception as e:
            log.debug(f"Could not get message_id for query generation: {e}")

    queries = []
    query_gen_start = time.perf_counter()
    try:
        res = await generate_queries(
            request,
            {
                "model": form_data["model"],
                "messages": messages,
                "prompt": user_message,
                "type": "web_search",
                "chat_id": chat_id,
                "message_id": message_id,  # May be None, recording will skip if missing
            },
            user,
        )

        response = res["choices"][0]["message"]["content"]

        try:
            bracket_start = response.find("{")
            bracket_end = response.rfind("}") + 1

            if bracket_start == -1 or bracket_end == -1:
                raise Exception("No JSON object found in the response")

            response = response[bracket_start:bracket_end]
            queries = json.loads(response)
            queries = queries.get("queries", [])
        except Exception as e:
            queries = [response]

    except Exception as e:
        log.exception(e)
        queries = [user_message]
    
    query_gen_time = time.perf_counter() - query_gen_start
    log.debug(f"PERF: chat_web_search_handler query generation took {query_gen_time:.3f}s, generated {len(queries)} queries")

    if len(queries) == 0:
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "web_search",
                    "description": "No search query generated",
                    "done": True,
                },
            }
        )
        return form_data

    all_results = []

    # Emit status for all searches starting
    for searchQuery in queries:
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "web_search",
                    "description": 'Searching "{{searchQuery}}"',
                    "query": searchQuery,
                    "done": False,
                },
            }
        )

    # Execute all searches in parallel with rate limiting
    # Use a semaphore to limit concurrent API calls (default 2 at a time to avoid rate limits, configurable via env)
    search_concurrency_limit = int(os.environ.get("WEB_SEARCH_CONCURRENCY_LIMIT", 2))
    search_semaphore = asyncio.Semaphore(search_concurrency_limit)
    
    async def execute_search(searchQuery, delay=0):
        # Stagger requests slightly to avoid hitting rate limits
        if delay > 0:
            await asyncio.sleep(delay)
        
        async with search_semaphore:
            search_start = time.perf_counter()
            try:
                results = await process_web_search(
                    request,
                    SearchForm(
                        **{
                            "query": searchQuery,
                            "chat_id": chat_id,
                            "message_id": message_id,
                        }
                    ),
                    user=user,
                )
                search_time = time.perf_counter() - search_start
                log.debug(f"PERF: process_web_search for query '{searchQuery[:50]}...' took {search_time:.3f}s")
                return searchQuery, results, None
            except Exception as e:
                search_time = time.perf_counter() - search_start
                log.exception(f"Error in parallel web search for query '{searchQuery[:50]}...': {e} (took {search_time:.3f}s)")
                await event_emitter(
                    {
                        "type": "status",
                        "data": {
                            "action": "web_search",
                            "description": 'Error searching "{{searchQuery}}"',
                            "query": searchQuery,
                            "done": True,
                            "error": True,
                        },
                    }
                )
                return searchQuery, None, e

    # Run all searches in parallel with staggered delays to avoid rate limits
    if queries:
        log.debug(f"PERF: chat_web_search_handler executing {len(queries)} web searches in parallel (rate-limited)")
        search_start = time.perf_counter()
        # Stagger requests: 0s, 0.5s, 1s delays to avoid hitting API rate limits
        search_tasks = [
            execute_search(query, delay=i * 0.5) 
            for i, query in enumerate(queries)
        ]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        search_total_time = time.perf_counter() - search_start
        log.debug(f"PERF: chat_web_search_handler parallel web searches took {search_total_time:.3f}s for {len(queries)} queries")

        # Process results
        files = form_data.get("files", [])
        for result in search_results:
            if isinstance(result, Exception):
                log.exception(f"Unexpected error in parallel web search: {result}")
                continue
            
            searchQuery, results, error = result
            if error:
                continue  # Already logged and emitted
            
            if results:
                all_results.append(results)

                if results.get("collection_names"):
                    for col_idx, collection_name in enumerate(
                        results.get("collection_names")
                    ):
                        files.append(
                            {
                                "collection_name": collection_name,
                                "name": searchQuery,
                                "type": "web_search",
                                "urls": [results["filenames"][col_idx]],
                            }
                        )
                elif results.get("docs"):
                    # Invoked when bypass embedding and retrieval is set to True
                    docs = results["docs"]

                    if len(docs) == len(results["filenames"]):
                        # the number of docs and filenames (urls) should be the same
                        for doc_idx, doc in enumerate(docs):
                            files.append(
                                {
                                    "docs": [doc],
                                    "name": searchQuery,
                                    "type": "web_search",
                                    "urls": [results["filenames"][doc_idx]],
                                }
                            )
                    else:
                        # edge case when the number of docs and filenames (urls) are not the same
                        # this should not happen, but if it does, we will just append the docs
                        files.append(
                            {
                                "docs": results.get("docs", []),
                                "name": searchQuery,
                                "type": "web_search",
                                "urls": results["filenames"],
                            }
                        )

        form_data["files"] = files

    if all_results:
        urls = []
        for results in all_results:
            if "filenames" in results:
                urls.extend(results["filenames"])

        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "web_search",
                    "description": "Searched {{count}} sites",
                    "urls": urls,
                    "done": True,
                },
            }
        )
    else:
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "web_search",
                    "description": "No search results found",
                    "done": True,
                    "error": True,
                },
            }
        )
    
    handler_total_time = time.perf_counter() - handler_start
    log.debug(f"PERF: chat_web_search_handler total time: {handler_total_time:.3f}s (processed {len(queries)} queries, {len(all_results)} results)")

    return form_data


async def chat_image_generation_handler(
    request: Request, form_data: dict, extra_params: dict, user
):
    __event_emitter__ = extra_params["__event_emitter__"]
    await __event_emitter__(
        {
            "type": "status",
            "data": {"description": "Generating an image", "done": False},
        }
    )

    messages = form_data["messages"]
    user_message = get_last_user_message(messages)

    prompt = user_message
    negative_prompt = ""

    if request.app.state.config.ENABLE_IMAGE_PROMPT_GENERATION:
        try:
            # Get chat_id and message_id for tracking
            chat_id = form_data.get("chat_id") or extra_params.get("__metadata__", {}).get("chat_id")
            message_id = None
            if chat_id:
                try:
                    # Get the last user message from the chat
                    all_messages = ChatMessages.get_all_messages_by_chat_id(chat_id)
                    user_messages = [m for m in all_messages if m.role == "user"]
                    if user_messages:
                        message_id = user_messages[-1].id
                except Exception as e:
                    log.debug(f"Could not get message_id for image prompt generation: {e}")

            res = await generate_image_prompt(
                request,
                {
                    "model": form_data["model"],
                    "messages": messages,
                    "chat_id": chat_id,
                    "message_id": message_id,  # May be None, recording will skip if missing
                },
                user,
            )

            response = res["choices"][0]["message"]["content"]

            try:
                bracket_start = response.find("{")
                bracket_end = response.rfind("}") + 1

                if bracket_start == -1 or bracket_end == -1:
                    raise Exception("No JSON object found in the response")

                response = response[bracket_start:bracket_end]
                response = json.loads(response)
                prompt = response.get("prompt", [])
            except Exception as e:
                prompt = user_message

        except Exception as e:
            log.exception(e)
            prompt = user_message

    system_message_content = ""

    try:
        images = await image_generations(
            request=request,
            form_data=GenerateImageForm(**{"prompt": prompt}),
            user=user,
        )

        await __event_emitter__(
            {
                "type": "status",
                "data": {"description": "Generated an image", "done": True},
            }
        )

        await __event_emitter__(
            {
                "type": "files",
                "data": {
                    "files": [
                        {
                            "type": "image",
                            "url": image["url"],
                        }
                        for image in images
                    ]
                },
            }
        )

        system_message_content = "<context>User is shown the generated image, tell the user that the image has been generated</context>"
    except Exception as e:
        log.exception(e)
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": f"An error occurred while generating an image",
                    "done": True,
                },
            }
        )

        system_message_content = "<context>Unable to generate an image, tell the user that an error occurred</context>"

    if system_message_content:
        form_data["messages"] = add_or_update_system_message(
            system_message_content, form_data["messages"]
        )

    return form_data


async def chat_completion_files_handler(
    request: Request, body: dict, user: UserModel
) -> tuple[dict, dict[str, list]]:
    sources = []

    if files := body.get("metadata", {}).get("files", None):
        queries = []
        try:
            # Try to get message_id for query generation tracking
            message_id = None
            chat_id = body.get("metadata", {}).get("chat_id")
            if chat_id:
                try:
                    # Get the last user message from the chat
                    all_messages = ChatMessages.get_all_messages_by_chat_id(chat_id)
                    user_messages = [m for m in all_messages if m.role == "user"]
                    if user_messages:
                        message_id = user_messages[-1].id
                except Exception as e:
                    log.debug(f"Could not get message_id for retrieval query generation: {e}")

            queries_response = await generate_queries(
                request,
                {
                    "model": body["model"],
                    "messages": body["messages"],
                    "type": "retrieval",
                    "chat_id": chat_id,
                    "message_id": message_id,  # May be None, recording will skip if missing
                },
                user,
            )
            queries_response = queries_response["choices"][0]["message"]["content"]

            try:
                bracket_start = queries_response.find("{")
                bracket_end = queries_response.rfind("}") + 1

                if bracket_start == -1 or bracket_end == -1:
                    raise Exception("No JSON object found in the response")

                queries_response = queries_response[bracket_start:bracket_end]
                queries_response = json.loads(queries_response)
            except Exception as e:
                queries_response = {"queries": [queries_response]}

            queries = queries_response.get("queries", [])
        except:
            pass

        if len(queries) == 0:
            queries = [get_last_user_message(body["messages"])]

        try:
            # Trust the frontend's file list - it already includes chat-level files + per-message files
            # The frontend builds this in sendPromptSocket: chatFiles + userMessage.files + responseMessage.files
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor() as executor:
                sources = await loop.run_in_executor(
                    executor,
                    lambda: get_sources_from_files(
                        request=request,
                        files=files,
                        queries=queries,
                        embedding_function=lambda query, prefix: request.app.state.EMBEDDING_FUNCTION(
                            query, prefix=prefix, user=user
                        ),
                        k=request.app.state.config.TOP_K,
                        reranking_function=request.app.state.rf,
                        k_reranker=request.app.state.config.TOP_K_RERANKER,
                        r=request.app.state.config.RELEVANCE_THRESHOLD,
                        hybrid_search=request.app.state.config.ENABLE_RAG_HYBRID_SEARCH,
                        full_context=request.app.state.config.RAG_FULL_CONTEXT,
                    ),
                )
        except Exception as e:
            log.exception(e)

        log.debug(f"rag_contexts:sources: {sources}")

    return body, {"sources": sources}


def apply_params_to_form_data(form_data, model):
    params = form_data.pop("params", {})
    if model.get("ollama"):
        form_data["options"] = params

        if "format" in params:
            form_data["format"] = params["format"]

        if "keep_alive" in params:
            form_data["keep_alive"] = params["keep_alive"]
    else:
        if "seed" in params and params["seed"] is not None:
            form_data["seed"] = params["seed"]

        if "stop" in params and params["stop"] is not None:
            form_data["stop"] = params["stop"]

        if "temperature" in params and params["temperature"] is not None:
            form_data["temperature"] = params["temperature"]

        if "max_tokens" in params and params["max_tokens"] is not None:
            form_data["max_tokens"] = params["max_tokens"]

        if "top_p" in params and params["top_p"] is not None:
            form_data["top_p"] = params["top_p"]

        if "frequency_penalty" in params and params["frequency_penalty"] is not None:
            form_data["frequency_penalty"] = params["frequency_penalty"]

        if "reasoning" in params and params["reasoning"] is not None:
            form_data["reasoning"] = params["reasoning"]

        # if "verbosity" in params and params["verbosity"] is not None:
        #     form_data["verbosity"] = params["verbosity"]

        if "provider" in params and params["provider"] is not None:
            # Transform provider parameters (convert comma-separated strings to arrays)
            provider_params = params["provider"]
            if isinstance(provider_params, dict):
                # Create a new dict with all original values
                transformed = {}
                for key, value in provider_params.items():
                    transformed[key] = value

                # Convert comma-separated strings to arrays
                for key in ['order', 'only', 'ignore']:
                    if key in transformed and transformed[key]:
                        if isinstance(transformed[key], str):
                            transformed[key] = [item.strip() for item in transformed[key].split(',') if item.strip()]

                # Handle boolean values
                for key in ['allow_fallbacks', 'require_parameters']:
                    if key in transformed and transformed[key] is not None:
                        if isinstance(transformed[key], str):
                            transformed[key] = transformed[key].lower() in ('true', '1', 'yes')

                # Handle string values (ensure they're stripped)
                for key in ['data_collection', 'sort']:
                    if key in transformed and transformed[key] is not None:
                        if isinstance(transformed[key], str):
                            transformed[key] = transformed[key].strip()

                form_data["provider"] = transformed
            else:
                form_data["provider"] = params["provider"]

        if "logit_bias" in params and params["logit_bias"] is not None:
            try:
                form_data["logit_bias"] = json.loads(
                    convert_logit_bias_input_to_json(params["logit_bias"])
                )
            except Exception as e:
                print(f"Error parsing logit_bias: {e}")

    return form_data


async def process_chat_payload(request, form_data, user, metadata, model):
    # Ensure messages exists from the start to prevent KeyError
    if "messages" not in form_data or form_data.get("messages") is None:
        form_data["messages"] = []

    form_data = apply_params_to_form_data(form_data, model)
    log.debug(f"form_data: {form_data}")

    event_emitter = get_event_emitter(metadata)
    event_call = get_event_call(metadata)

    extra_params = {
        "__event_emitter__": event_emitter,
        "__event_call__": event_call,
        "__user__": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        },
        "__metadata__": metadata,
        "__request__": request,
        "__model__": model,
    }

    # Initialize events to store additional event to be sent to the client
    # Initialize contexts and citation
    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    task_model_id = get_task_model_id(
        form_data["model"],
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    events = []
    sources = []

    # Ensure messages exist; if missing or empty, rebuild from normalized storage
    # Only rebuild if messages is actually missing (not just empty)
    if "messages" not in form_data or form_data.get("messages") is None:
        try:
            chat_id = metadata.get("chat_id")
            # Use parent chain of the user message; if message_id refers to assistant, hop to parent
            leaf_id = metadata.get("message_id")
            if leaf_id:
                leaf = ChatMessages.get_message_by_id(leaf_id)
                parent_id = leaf.parent_id if leaf else None
            else:
                parent_id = None
            branch = []
            if chat_id and parent_id:
                branch = ChatMessages.get_branch_to_root(chat_id, parent_id)
            # Convert to OpenAI-style messages with image_url content
            rebuilt = []
            for m in branch:
                content = m.content_text or ""
                items = []
                if content:
                    items.append({"type": "text", "text": content})
                # attachments are added later during image resolution if present in frontend; we skip here
                rebuilt.append({
                    "role": m.role,
                    "content": content if items == [] else items
                })
            if rebuilt:
                form_data["messages"] = rebuilt
        except Exception as e:
            log.debug(f"Failed to rebuild messages from normalized storage: {e}")

    # Ensure messages is always a list, even if empty or missing
    if "messages" not in form_data or form_data["messages"] is None:
        form_data["messages"] = []

    # Compute _request_files BEFORE processing user messages so files are available when we need them
    # This determines which files should be attached to the user message
    files = form_data.get("files", [])
    chat_id = metadata.get("chat_id")
    new_request_files: list[dict] = []
    if files and chat_id:
        all_request_files = [f for f in files if isinstance(f, dict)]

        try:
            from open_webui.models.chat_messages import ChatMessage, ChatMessageAttachment
            from open_webui.internal.db import get_db

            # Get files already in chat.files
            chat_model = Chats.get_chat_by_id(chat_id)
            existing_chat_files: list[dict] = []
            if chat_model and chat_model.chat and isinstance(chat_model.chat, dict):
                existing_chat_files = chat_model.chat.get("files", []) or []

            # Get all files already attached to messages in this chat
            with get_db() as db:
                # Get all user messages in this chat
                attached_messages = db.query(ChatMessage).filter_by(
                    chat_id=chat_id,
                    role="user"
                ).all()

                # Collect all file IDs/keys from message attachments and meta
                attached_file_keys = set()
                for msg in attached_messages:
                    # Check message meta for files
                    msg_meta = msg.meta if hasattr(msg, 'meta') else None
                    if msg_meta and isinstance(msg_meta, dict) and "files" in msg_meta:
                        msg_files = msg_meta.get("files", [])
                        if isinstance(msg_files, list):
                            for f in msg_files:
                                if isinstance(f, dict):
                                    file_id = f.get("id") or f.get("collection_name") or (f.get("meta") or {}).get("collection_name")
                                    file_type = f.get("type", "file")
                                    if file_id:
                                        attached_file_keys.add((file_type, file_id))

                # Check message attachments table directly
                message_ids = [msg.id for msg in attached_messages]
                if message_ids:
                    attachments = db.query(ChatMessageAttachment).filter(
                        ChatMessageAttachment.message_id.in_(message_ids)
                    ).all()
                    for att in attachments:
                        if att.file_id:
                            attached_file_keys.add((att.type or "file", att.file_id))
                        elif att.url and isinstance(att.url, str) and "/files/" in att.url:
                            # Extract file_id from URL
                            match = re.search(r"/files/([A-Za-z0-9\-]+)", att.url)
                            if match:
                                attached_file_keys.add((att.type or "file", match.group(1)))

            def _file_key(file_item: dict) -> tuple:
                if not isinstance(file_item, dict):
                    return (None, None)
                meta = file_item.get("meta") or {}
                file_id = file_item.get("id") or file_item.get("collection_name") or meta.get("collection_name")
                return (file_item.get("type", "file"), file_id)

            # Files that should be attached: in chat.files but not yet attached to any message
            existing_chat_keys = {_file_key(f) for f in existing_chat_files if isinstance(f, dict)}
            for file_item in all_request_files:
                file_key = _file_key(file_item)
                # Attach if: file is in chat.files AND not yet attached to any message
                if file_key in existing_chat_keys and file_key not in attached_file_keys:
                    new_request_files.append(file_item)
                elif file_key not in existing_chat_keys:
                    # File is new to chat entirely - attach it
                    new_request_files.append(file_item)
        except Exception as e:
            log.debug(f"Error checking attached files for chat {chat_id}: {e}", exc_info=True)
            # Fallback: if we can't check, don't attach any files (safer than duplicating)
            new_request_files = []

    # Store _request_files in metadata so it's available when processing user messages
    metadata["_request_files"] = new_request_files

    # Insert user message into normalized database if we have chat_id and a user message
    if chat_id and form_data.get("messages"):
        try:
            # Find the last user message to insert
            user_msg = get_last_user_message_item(form_data["messages"])
            if user_msg:
                # Extract content and attachments
                content_text = None
                content_json = None
                attachments = []

                content = user_msg.get("content")
                if isinstance(content, str):
                    content_text = content
                elif isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            if content_text:
                                content_text += "\n" + item.get("text", "")
                            else:
                                content_text = item.get("text", "")
                        elif item.get("type") == "image_url":
                            url = (item.get("image_url") or {}).get("url", "")
                            # Extract file_id from URL if it's an internal file URL
                            if url and "/files/" in url:
                                file_match = re.search(r"/files/([A-Za-z0-9\-]+)", url)
                                if file_match:
                                    file_id = file_match.group(1)
                                    file_model = Files.get_file_by_id(file_id)
                                    if file_model:
                                        file_meta = file_model.meta or {}
                                        file_data = file_model.data or {}
                                        attachments.append({
                                            "type": "image",
                                            "file_id": file_id,
                                            "url": url,
                                            "mime_type": file_meta.get("content_type") or file_data.get("content_type"),
                                            "size_bytes": file_meta.get("size"),
                                            "metadata": file_meta  # Store full file meta
                                        })
                    # If we have a list with no text, store as JSON
                    if not content_text and content:
                        content_json = {"items": content}

                # Attach files explicitly provided on this user message.
                # We only attach files that the frontend marked on this specific user message.
                request_files = metadata.get("_request_files", [])
                user_msg_files = user_msg.get("files", [])  # Files from message object (may be empty)
                user_meta = None

                files_to_attach: list[dict] = []
                # Priority 1: Files explicitly in user_msg.files (explicitly attached to this message)
                if isinstance(user_msg_files, list) and user_msg_files:
                    files_to_attach = [f for f in user_msg_files if isinstance(f, dict)]
                # Priority 2: Files that are new to the chat (not already in chat.files)
                elif isinstance(request_files, list) and request_files:
                    files_to_attach = [f for f in request_files if isinstance(f, dict)]

                meta_files = []
                if files_to_attach:
                    for file_item in files_to_attach:
                        file_type = file_item.get("type", "file")
                        file_id = file_item.get("id")

                        # Build attachment metadata preserving all fields
                        attachment_meta = {}
                        if "meta" in file_item and isinstance(file_item["meta"], dict):
                            attachment_meta.update(file_item["meta"])
                        # Copy top-level fields that should be preserved
                        # For collections, include id and other important fields (but NOT files or data.file_ids)
                        fields_to_copy = ["name", "description", "status", "collection", "collection_name", "collection_names"]
                        if file_type == "collection":
                            # For collections, copy id and other collection-specific fields, but exclude files and data.file_ids
                            fields_to_copy.extend(["id", "user_id", "user", "access_control", "created_at", "updated_at"])
                            # Copy data but exclude file_ids from it
                            if "data" in file_item and isinstance(file_item["data"], dict):
                                data_copy = {k: v for k, v in file_item["data"].items() if k != "file_ids"}
                                if data_copy:  # Only add data if there are other fields besides file_ids
                                    attachment_meta["data"] = data_copy
                        for key in fields_to_copy:
                            if key in file_item:
                                attachment_meta[key] = file_item[key]

                        # Create attachment dict
                        att_dict = {
                            "type": file_type,
                            "file_id": file_id if file_type not in ["collection", "web_search"] else None,
                            "url": file_item.get("url") if file_type not in ["collection", "web_search"] else None,
                            "mime_type": file_item.get("mime_type"),
                            "size_bytes": file_item.get("size_bytes"),
                            "metadata": attachment_meta if attachment_meta else {}
                        }
                        attachments.append(att_dict)

                        # Preserve full file metadata for the message meta (deep copy to avoid mutation)
                        sanitized = deepcopy(file_item)
                        # Avoid storing large in-memory data blobs on the message meta
                        if isinstance(sanitized.get("data"), (bytes, bytearray)):
                            sanitized.pop("data", None)
                        if isinstance(sanitized.get("file"), dict):
                            sanitized["file"] = {
                                k: v for k, v in sanitized["file"].items() if k != "data"
                            }
                        # For collections, strip files array and data.file_ids
                        if file_type == "collection":
                            sanitized.pop("files", None)
                            if isinstance(sanitized.get("data"), dict):
                                sanitized["data"].pop("file_ids", None)
                                # Remove data entirely if it's now empty
                                if not sanitized["data"]:
                                    sanitized.pop("data", None)
                        meta_files.append(sanitized)

                if meta_files:
                    user_meta = user_meta.copy() if user_meta else {}
                    user_meta["files"] = meta_files
                metadata.pop("_request_files", None)

                # Get parent_id from the message structure if available
                # Convert to string to ensure consistent format
                parent_id_raw = user_msg.get("parent_id") or user_msg.get("parentId")
                parent_id = str(parent_id_raw) if parent_id_raw is not None else None

                # Frontend-provided user message ID (use it if provided)
                # Convert to string to ensure consistent format
                frontend_user_id_raw = user_msg.get("id")
                frontend_user_id = str(frontend_user_id_raw) if frontend_user_id_raw is not None else None

                # For side-by-side chats: check if a user message with the same content already exists recently
                # This prevents duplicate user messages when multiple models respond to the same prompt
                should_insert_user = True
                existing_user_message_id = None

                if frontend_user_id:
                    existing = ChatMessages.get_message_by_id(frontend_user_id)
                    if existing:
                        should_insert_user = False
                        user_message_id = existing.id
                        # Use the existing message's parent_id to maintain sibling relationships
                        parent_id = existing.parent_id
                        # Update existing message with files and attachments if we have them
                        if (meta_files and len(meta_files) > 0) or (attachments and len(attachments) > 0):
                            # Update meta with files
                            if meta_files and len(meta_files) > 0:
                                update_meta = user_meta.copy() if user_meta else {}
                                if "files" not in update_meta:
                                    update_meta["files"] = meta_files
                                ChatMessages.update_message(user_message_id, meta=update_meta)
                            # Add attachments if they don't already exist
                            if attachments and len(attachments) > 0:
                                from open_webui.models.chat_messages import ChatMessageAttachment
                                from open_webui.internal.db import get_db
                                with get_db() as db:
                                    # Check which attachments already exist
                                    existing_attachments = db.query(ChatMessageAttachment).filter_by(
                                        message_id=user_message_id
                                    ).all()
                                    existing_att_keys = set()
                                    for att in existing_attachments:
                                        if att.file_id:
                                            existing_att_keys.add((att.type or "file", att.file_id))
                                        elif att.url and isinstance(att.url, str) and "/files/" in att.url:
                                            match = re.search(r"/files/([A-Za-z0-9\-]+)", att.url)
                                            if match:
                                                existing_att_keys.add((att.type or "file", match.group(1)))
                                    # Add new attachments
                                    for att_dict in attachments:
                                        att_type = att_dict.get("type", "file")
                                        att_file_id = att_dict.get("file_id")
                                        att_key = (att_type, att_file_id) if att_file_id else None
                                        if att_key and att_key not in existing_att_keys:
                                            ChatMessages.add_attachment(user_message_id, att_dict)
                    else:
                        user_message_id = None
                else:
                    user_message_id = None

                # If we don't have an existing message by ID, check for duplicate content (side-by-side scenario)
                # BUT: Only use duplicate detection if we don't have a frontend-provided ID
                # If frontend provided an ID, we should use it even if content is duplicate (to preserve ID consistency)
                if should_insert_user and content_text and not frontend_user_id:
                    from open_webui.internal.db import get_db
                    from open_webui.models.chat_messages import ChatMessage
                    from sqlalchemy import and_

                    with get_db() as db:
                        # Look for a user message with the same content created within the last 30 seconds
                        recent_cutoff = int(time.time()) - 30
                        duplicate = db.query(ChatMessage).filter(
                            and_(
                                ChatMessage.chat_id == chat_id,
                                ChatMessage.role == "user",
                                ChatMessage.content_text == content_text,
                                ChatMessage.created_at >= recent_cutoff
                            )
                        ).order_by(ChatMessage.created_at.desc()).first()

                        if duplicate:
                            # Reuse the existing user message for side-by-side chats
                            should_insert_user = False
                            existing_user_message_id = duplicate.id
                            user_message_id = duplicate.id
                            # Use the duplicate's parent_id to maintain correct hierarchy
                            # Access the SQLAlchemy model attribute directly
                            parent_id = duplicate.parent_id if duplicate.parent_id else None
                            # Update existing message with files and attachments if we have them
                            if (meta_files and len(meta_files) > 0) or (attachments and len(attachments) > 0):
                                # Update meta with files
                                if meta_files and len(meta_files) > 0:
                                    update_meta = user_meta.copy() if user_meta else {}
                                    if "files" not in update_meta:
                                        update_meta["files"] = meta_files
                                    ChatMessages.update_message(user_message_id, meta=update_meta)
                                # Add attachments if they don't already exist
                                if attachments and len(attachments) > 0:
                                    from open_webui.models.chat_messages import ChatMessageAttachment
                                    from open_webui.internal.db import get_db
                                    with get_db() as db_att:
                                        # Check which attachments already exist
                                        existing_attachments = db_att.query(ChatMessageAttachment).filter_by(
                                            message_id=user_message_id
                                        ).all()
                                        existing_att_keys = set()
                                        for att in existing_attachments:
                                            if att.file_id:
                                                existing_att_keys.add((att.type or "file", att.file_id))
                                            elif att.url and isinstance(att.url, str) and "/files/" in att.url:
                                                match = re.search(r"/files/([A-Za-z0-9\-]+)", att.url)
                                                if match:
                                                    existing_att_keys.add((att.type or "file", match.group(1)))
                                        # Add new attachments
                                        for att_dict in attachments:
                                            att_type = att_dict.get("type", "file")
                                            att_file_id = att_dict.get("file_id")
                                            att_key = (att_type, att_file_id) if att_file_id else None
                                            if att_key and att_key not in existing_att_keys:
                                                ChatMessages.add_attachment(user_message_id, att_dict)

                # Validate parent_id exists in database if provided
                # If parent_id is provided but doesn't exist, it might be a frontend ID that wasn't saved correctly
                # In that case, we should try to find the message by other means (e.g., by content/timestamp)
                if should_insert_user and parent_id:
                    parent_msg = ChatMessages.get_message_by_id(parent_id)
                    if not parent_msg:
                        log.debug(f"Parent message {parent_id} not found in database for chat {chat_id}. Attempting to fall back to last assistant message.")
                        # Fallback: use the most recent assistant message in this chat as parent
                        try:
                            with get_db() as db:
                                last_assistant = (
                                    db.query(ChatMessage)
                                    .filter_by(chat_id=chat_id, role="assistant")
                                    .order_by(ChatMessage.created_at.desc())
                                    .first()
                                )
                                if last_assistant:
                                    parent_id = str(last_assistant.id)
                                    log.debug(f"Using last assistant message {parent_id} as parent fallback")
                                else:
                                    # As a final fallback, use active_message_id if valid
                                    chat_model = Chats.get_chat_by_id(chat_id)
                                    if chat_model and chat_model.active_message_id:
                                        active_msg = ChatMessages.get_message_by_id(chat_model.active_message_id)
                                        if active_msg:
                                            parent_id = str(chat_model.active_message_id)
                                            log.debug(f"Using active_message_id {parent_id} as parent fallback")
                        except Exception as e:
                            log.debug(f"Fallback parent resolution failed: {e}")
                    else:
                        # Parent exists - verify the ID matches (should be string)
                        if str(parent_msg.id) != str(parent_id):
                            log.debug(f"Parent ID mismatch: requested {parent_id}, got {parent_msg.id}")
                            parent_id = str(parent_msg.id)

                # If parent_id is still not set and we're inserting, try to get it from chat's active_message_id
                # For side-by-side chats, the frontend sets parent_id to the selected assistant message
                # so we should trust the parent_id from the user message payload
                # Only fall back to chat metadata if parent_id wasn't provided
                if should_insert_user and not parent_id:
                    chat_model = Chats.get_chat_by_id(chat_id)
                    if chat_model:
                        # Use active_message_id if it exists and is an assistant message (for continuing side-by-side)
                        # or if it's a user message (for standard continuation)
                        if chat_model.active_message_id:
                            active_msg = ChatMessages.get_message_by_id(chat_model.active_message_id)
                            if active_msg:
                                # Allow both user and assistant messages as parents
                                # User message parent = standard continuation
                                # Assistant message parent = side-by-side continuation from specific response
                                parent_id = str(chat_model.active_message_id)
                        elif chat_model.root_message_id:
                            # Fallback to root_message_id if active_message_id is not set
                            root_msg = ChatMessages.get_message_by_id(chat_model.root_message_id)
                            if root_msg and root_msg.role == "user":
                                parent_id = str(chat_model.root_message_id)

                # Extract models array from user message for side-by-side chats
                # This is stored in the user message's "models" property in the frontend
                # First try to get it from the user message in the payload
                user_models = user_msg.get("models")

                # If not in the message, try to get it from chat.chat["models"] (stored at chat level)
                if not user_models:
                    chat_model = Chats.get_chat_by_id(chat_id)
                    if chat_model and chat_model.chat:
                        # Check if models are stored in chat.chat (the JSON blob)
                        user_models = chat_model.chat.get("models")
                    # Also check params as fallback
                    if not user_models and chat_model and chat_model.params:
                        user_models = chat_model.params.get("models")

                if user_models:
                    user_meta = user_meta.copy() if user_meta else {}
                    user_meta["models"] = user_models

                # Insert user message if needed
                if should_insert_user:
                    # Ensure parent_id and frontend_user_id are strings
                    parent_id_str = str(parent_id) if parent_id else None
                    frontend_user_id_str = str(frontend_user_id) if frontend_user_id else None

                    inserted_user = ChatMessages.insert_message(chat_id, MessageCreateForm(
                        parent_id=parent_id_str,
                        role="user",
                        content_text=content_text,
                        content_json=content_json,
                        model_id=None,
                        attachments=attachments if attachments else None,
                        meta=user_meta
                    ), message_id=frontend_user_id_str)
                    if inserted_user:
                        user_message_id = inserted_user.id
                        # If this is the first message (no parent), set it as root_message_id
                        if not parent_id:
                            Chats.update_chat_active_and_root_message_ids(chat_id, root_message_id=user_message_id)

                # Insert assistant placeholder if we have message_id and it doesn't exist
                assistant_id = metadata.get("message_id")
                if assistant_id:
                    existing_assistant = ChatMessages.get_message_by_id(assistant_id)
                    if not existing_assistant and user_message_id:
                        # Extract modelIdx from metadata for side-by-side chats
                        # modelIdx indicates which position in the user's models array this response corresponds to
                        model_idx = metadata.get("modelIdx")
                        assistant_meta = None
                        position_for_assistant = None
                        if model_idx is not None:
                            assistant_meta = {"modelIdx": model_idx}
                            # Use modelIdx as position for side-by-side chats to ensure correct ordering
                            # This prevents race conditions when multiple messages are created simultaneously
                            position_for_assistant = model_idx

                        # For side-by-side chats, use modelIdx as position to ensure correct ordering
                        # Ensure user_message_id and assistant_id are strings
                        user_message_id_str = str(user_message_id) if user_message_id else None
                        assistant_id_str = str(assistant_id) if assistant_id else None

                        ChatMessages.insert_message(
                            chat_id,
                            MessageCreateForm(
                                parent_id=user_message_id_str,
                                role="assistant",
                                content_text="",
                                content_json=None,
                                model_id=form_data.get("model"),
                                attachments=None,
                                meta=assistant_meta,
                                position=position_for_assistant,
                            ),
                            message_id=assistant_id_str,
                        )
                        # Update active_message_id to point to this assistant message
                        Chats.update_chat_active_and_root_message_ids(chat_id, active_message_id=assistant_id_str)
        except Exception as e:
            log.debug(f"Failed to insert messages into normalized storage: {e}")

    user_message = get_last_user_message(form_data["messages"])
    model_knowledge = model.get("info", {}).get("meta", {}).get("knowledge", False)

    if model_knowledge:
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "knowledge_search",
                    "query": user_message,
                    "done": False,
                },
            }
        )

        knowledge_files = []
        for item in model_knowledge:
            if item.get("collection_name"):
                knowledge_files.append(
                    {
                        "id": item.get("collection_name"),
                        "name": item.get("name"),
                        "legacy": True,
                    }
                )
            elif item.get("collection_names"):
                knowledge_files.append(
                    {
                        "name": item.get("name"),
                        "type": "collection",
                        "collection_names": item.get("collection_names"),
                        "legacy": True,
                    }
                )
            else:
                knowledge_files.append(item)

        files = form_data.get("files", [])
        files.extend(knowledge_files)
        form_data["files"] = files

    variables = form_data.pop("variables", None)

    # Process the form_data through the pipeline
    try:
        form_data = await process_pipeline_inlet_filter(
            request, form_data, user, models
        )
    except Exception as e:
        raise e

    try:
        filter_functions = [
            Functions.get_function_by_id(filter_id)
            for filter_id in get_sorted_filter_ids(model)
        ]

        form_data, flags = await process_filter_functions(
            request=request,
            filter_functions=filter_functions,
            filter_type="inlet",
            form_data=form_data,
            extra_params=extra_params,
        )
    except Exception as e:
        raise Exception(f"Error: {e}")

    features = form_data.pop("features", None)
    if features:
        if "web_search" in features and features["web_search"]:
            form_data = await chat_web_search_handler(
                request, form_data, extra_params, user
            )

        if "image_generation" in features and features["image_generation"]:
            form_data = await chat_image_generation_handler(
                request, form_data, extra_params, user
            )

        if "code_interpreter" in features and features["code_interpreter"]:
            form_data["messages"] = add_or_update_user_message(
                (
                    request.app.state.config.CODE_INTERPRETER_PROMPT_TEMPLATE
                    if request.app.state.config.CODE_INTERPRETER_PROMPT_TEMPLATE != ""
                    else DEFAULT_CODE_INTERPRETER_PROMPT
                ),
                form_data["messages"],
            )

    tool_ids = form_data.pop("tool_ids", None)
    files = form_data.pop("files", None)

    # Remove files duplicates
    if files:
        files = list({json.dumps(f, sort_keys=True): f for f in files}.values())

    metadata = {
        **metadata,
        "tool_ids": tool_ids,
        "files": files,
    }
    # _request_files was already computed earlier, before user message processing
    # Just ensure it's in metadata
    if "_request_files" not in metadata:
        metadata["_request_files"] = []
    form_data["metadata"] = metadata

    # Server side tools
    tool_ids = metadata.get("tool_ids", None)
    # Client side tools
    tool_servers = metadata.get("tool_servers", None)

    log.debug(f"{tool_ids=}")
    log.debug(f"{tool_servers=}")

    tools_dict = {}

    if tool_ids:
        tools_dict = get_tools(
            request,
            tool_ids,
            user,
            {
                **extra_params,
                "__model__": models[task_model_id],
                "__messages__": form_data["messages"],
                "__files__": metadata.get("files", []),
            },
        )

    if tool_servers:
        for tool_server in tool_servers:
            tool_specs = tool_server.pop("specs", [])

            for tool in tool_specs:
                tools_dict[tool["name"]] = {
                    "spec": tool,
                    "direct": True,
                    "server": tool_server,
                }

    if tools_dict:
        if metadata.get("function_calling") == "native":
            # If the function calling is native, then call the tools function calling handler
            metadata["tools"] = tools_dict
            form_data["tools"] = [
                {"type": "function", "function": tool.get("spec", {})}
                for tool in tools_dict.values()
            ]
        else:
            # If the function calling is not native, then call the tools function calling handler
            try:
                form_data, flags = await chat_completion_tools_handler(
                    request, form_data, extra_params, user, models, tools_dict
                )
                sources.extend(flags.get("sources", []))

            except Exception as e:
                log.exception(e)

    try:
        form_data, flags = await chat_completion_files_handler(request, form_data, user)
        sources.extend(flags.get("sources", []))
    except Exception as e:
        log.exception(e)
    # If context is not empty, insert it into the messages
    if len(sources) > 0:
        context_string = ""
        citated_file_idx = {}
        for _, source in enumerate(sources, 1):
            if "document" in source:
                for doc_context, doc_meta in zip(
                    source["document"], source["metadata"]
                ):
                    file_id = doc_meta.get("file_id")
                    if file_id not in citated_file_idx:
                        citated_file_idx[file_id] = len(citated_file_idx) + 1
                    context_string += f'<source id="{citated_file_idx[file_id]}">{doc_context}</source>\n'

        context_string = context_string.strip()
        prompt = get_last_user_message(form_data["messages"])

        if prompt is None:
            raise Exception("No user message found")
        if (
            request.app.state.config.RELEVANCE_THRESHOLD == 0
            and context_string.strip() == ""
        ):
            log.debug(
                f"With a 0 relevancy threshold for RAG, the context cannot be empty"
            )

        # Workaround for Ollama 2.0+ system prompt issue
        # TODO: replace with add_or_update_system_message
        if model.get("owned_by") == "ollama":
            form_data["messages"] = prepend_to_first_user_message_content(
                rag_template(
                    request.app.state.config.RAG_TEMPLATE, context_string, prompt
                ),
                form_data["messages"],
            )
        else:
            form_data["messages"] = add_or_update_system_message(
                rag_template(
                    request.app.state.config.RAG_TEMPLATE, context_string, prompt
                ),
                form_data["messages"],
            )

    # If there are citations, add them to the data_items
    sources = [source for source in sources if source.get("source", {}).get("name", "")]

    if len(sources) > 0:
        events.append({"sources": sources})

    if model_knowledge:
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "knowledge_search",
                    "query": user_message,
                    "done": True,
                    "hidden": True,
                },
            }
        )

    # Convert internal file URLs in image_url blocks to Base64 for provider compatibility
    try:
        form_data["messages"] = await _resolve_message_image_urls_to_base64(
            request, form_data.get("messages", [])
        )
    except Exception as e:
        log.debug(f"_resolve_message_image_urls_to_base64 error: {e}")

    return form_data, metadata, events


async def _resolve_message_image_urls_to_base64(request: Request, messages: list[dict]) -> list[dict]:
    """
    Transform any message content items of type image_url that reference internal
    /api/v1/files/{id} (optionally with /content suffix) into Base64 data URIs so
    providers that require inline images receive them without the frontend sending Base64.
    """
    if not isinstance(messages, list):
        return messages

    # Precompile regex to extract file id from URL
    file_id_regex = re.compile(r"/files/([A-Za-z0-9\-]+)")

    def to_data_uri(file_model) -> Optional[str]:
        try:
            file_path = Storage.get_file(file_model.path)
            with open(file_path, "rb") as f:
                raw = f.read()
            mime = (
                (file_model.meta or {}).get("content_type")
                or (file_model.data or {}).get("content_type")
                or "image/png"
            )
            return f"data:{mime};base64,{base64.b64encode(raw).decode('utf-8')}"
        except Exception as e:
            log.debug(f"Failed to load file bytes for image embedding: {e}")
            return None

    resolved: list[dict] = []
    for message in messages:
        msg = message
        content = msg.get("content")
        if isinstance(content, list):
            new_items = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    url = (item.get("image_url") or {}).get("url", "")
                    if url and not url.startswith("data:"):
                        match = file_id_regex.search(url)
                        if match:
                            file_id = match.group(1)
                            file_model = Files.get_file_by_id(file_id)
                            if file_model:
                                data_uri = to_data_uri(file_model)
                                if data_uri:
                                    item = {"type": "image_url", "image_url": {"url": data_uri}}
                new_items.append(item)
            msg = {**msg, "content": new_items}
        resolved.append(msg)

    return resolved


async def process_chat_response(
    request, response, form_data, user, metadata, model, events, tasks
):
    async def background_tasks_handler():
        message_map = Chats.get_messages_by_chat_id(metadata["chat_id"])
        message = message_map.get(metadata["message_id"]) if message_map else None

        if message:
            messages = get_message_list(message_map, message.get("id"))

            if tasks and messages:
                if TASKS.TITLE_GENERATION in tasks:
                    if tasks[TASKS.TITLE_GENERATION]:
                        res = await generate_title(
                            request,
                            {
                                "model": message["model"],
                                "messages": messages,
                                "chat_id": metadata["chat_id"],
                                "message_id": metadata["message_id"],  # Assistant message ID
                            },
                            user,
                        )

                        if res and isinstance(res, dict):
                            if len(res.get("choices", [])) == 1:
                                title_string = (
                                    res.get("choices", [])[0]
                                    .get("message", {})
                                    .get("content", message.get("content", "New Chat"))
                                )
                            else:
                                title_string = ""

                            title_string = title_string[
                                title_string.find("{") : title_string.rfind("}") + 1
                            ]

                            try:
                                title = json.loads(title_string).get(
                                    "title", "New Chat"
                                )
                            except Exception as e:
                                title = ""

                            if not title:
                                title = messages[0].get("content", "New Chat")

                            Chats.update_chat_title_by_id(metadata["chat_id"], title)

                            await event_emitter(
                                {
                                    "type": "chat:title",
                                    "data": title,
                                }
                            )
                    elif len(messages) == 2:
                        title = messages[0].get("content", "New Chat")

                        Chats.update_chat_title_by_id(metadata["chat_id"], title)

                        await event_emitter(
                            {
                                "type": "chat:title",
                                "data": message.get("content", "New Chat"),
                            }
                        )

                if TASKS.TAGS_GENERATION in tasks and tasks[TASKS.TAGS_GENERATION]:
                    res = await generate_chat_tags(
                        request,
                        {
                            "model": message["model"],
                            "messages": messages,
                            "chat_id": metadata["chat_id"],
                            "message_id": metadata["message_id"],  # Assistant message ID
                        },
                        user,
                    )

                    if res and isinstance(res, dict):
                        if len(res.get("choices", [])) == 1:
                            tags_string = (
                                res.get("choices", [])[0]
                                .get("message", {})
                                .get("content", "")
                            )
                        else:
                            tags_string = ""

                        tags_string = tags_string[
                            tags_string.find("{") : tags_string.rfind("}") + 1
                        ]

                        try:
                            tags = json.loads(tags_string).get("tags", [])
                            Chats.update_chat_tags_by_id(
                                metadata["chat_id"], tags, user
                            )

                            await event_emitter(
                                {
                                    "type": "chat:tags",
                                    "data": tags,
                                }
                            )
                        except Exception as e:
                            pass

    event_emitter = None
    event_caller = None
    if (
        "session_id" in metadata
        and metadata["session_id"]
        and "chat_id" in metadata
        and metadata["chat_id"]
        and "message_id" in metadata
        and metadata["message_id"]
    ):
        event_emitter = get_event_emitter(metadata)
        event_caller = get_event_call(metadata)

    # Non-streaming response
    if not isinstance(response, StreamingResponse):
        if event_emitter:
            if "error" in response:
                error = response["error"].get("detail", response["error"])
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {
                        "error": {"content": error},
                    },
                )
                # Update normalized table
                try:
                    ChatMessages.update_message(
                        metadata["message_id"],
                        meta={"error": {"content": error}}
                    )
                except Exception as e:
                    log.debug(f"Failed to update normalized message error: {e}")

            if "selected_model_id" in response:
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {
                        "selectedModelId": response["selected_model_id"],
                    },
                )
                # Update normalized table
                try:
                    ChatMessages.update_message(
                        metadata["message_id"],
                        meta={"selectedModelId": response["selected_model_id"]}
                    )
                except Exception as e:
                    log.debug(f"Failed to update normalized message selectedModelId: {e}")

            choices = response.get("choices", [])
            if choices and choices[0].get("message", {}).get("content"):
                content = response["choices"][0]["message"]["content"]

                if content:

                    await event_emitter(
                        {
                            "type": "chat:completion",
                            "data": response,
                        }
                    )

                    title = Chats.get_chat_title_by_id(metadata["chat_id"])

                    await event_emitter(
                        {
                            "type": "chat:completion",
                            "data": {
                                "done": True,
                                "content": content,
                                "title": title,
                            },
                        }
                    )

                    # Save message in the database
                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        metadata["message_id"],
                        {
                            "content": content,
                        },
                    )
                    # Update normalized table with content and usage
                    try:
                        usage = response.get("usage")
                        result = ChatMessages.update_message(
                            metadata["message_id"],
                            content_text=content,
                            usage=usage
                        )
                        if not result:
                            log.warning(f"Failed to update normalized message {metadata['message_id']}: message not found in normalized table")
                        # Update active_message_id to point to this completed message
                        if result:
                            Chats.update_chat_active_and_root_message_ids(metadata["chat_id"], active_message_id=metadata["message_id"])
                    except Exception as e:
                        log.error(f"Failed to update normalized message content: {e}", exc_info=True)

                    # Send a webhook notification if the user is not active
                    if get_active_status_by_user_id(user.id) is None:
                        webhook_url = Users.get_user_webhook_url_by_id(user.id)
                        if webhook_url:
                            post_webhook(
                                request.app.state.WEBUI_NAME,
                                webhook_url,
                                f"{title} - {request.app.state.config.WEBUI_URL}/c/{metadata['chat_id']}\n\n{content}",
                                {
                                    "action": "chat",
                                    "message": content,
                                    "title": title,
                                    "url": f"{request.app.state.config.WEBUI_URL}/c/{metadata['chat_id']}",
                                },
                            )

                    await background_tasks_handler()

            return response
        else:
            return response

    # Non standard response
    if not any(
        content_type in response.headers["Content-Type"]
        for content_type in ["text/event-stream", "application/x-ndjson"]
    ):
        return response

    extra_params = {
        "__event_emitter__": event_emitter,
        "__event_call__": event_caller,
        "__user__": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        },
        "__metadata__": metadata,
        "__request__": request,
        "__model__": model,
    }
    filter_functions = [
        Functions.get_function_by_id(filter_id)
        for filter_id in get_sorted_filter_ids(model)
    ]

    # Streaming response
    if event_emitter and event_caller:
        task_id = str(uuid4())  # Create a unique task ID.
        model_id = form_data.get("model", "")

        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            {
                "model": model_id,
            },
        )
        # Update normalized table
        try:
            ChatMessages.update_message(
                metadata["message_id"],
                model_id=model_id,
                skip_metrics_rollup=ENABLE_REALTIME_CHAT_SAVE,
            )
        except Exception as e:
            log.debug(f"Failed to update normalized message model_id: {e}")

        def split_content_and_whitespace(content):
            content_stripped = content.rstrip()
            original_whitespace = (
                content[len(content_stripped) :]
                if len(content) > len(content_stripped)
                else ""
            )
            return content_stripped, original_whitespace

        def is_opening_code_block(content):
            backtick_segments = content.split("```")
            # Even number of segments means the last backticks are opening a new block
            return len(backtick_segments) > 1 and len(backtick_segments) % 2 == 0

        # Handle as a background task
        async def post_response_handler(response, events):
            def serialize_content_blocks(content_blocks, raw=False):
                content = ""

                for block in content_blocks:
                    if block["type"] == "text":
                        content = f"{content}{block['content'].strip()}\n"
                    elif block["type"] == "tool_calls":
                        attributes = block.get("attributes", {})

                        tool_calls = block.get("content", [])
                        results = block.get("results", [])

                        if results:

                            tool_calls_display_content = ""
                            for tool_call in tool_calls:

                                tool_call_id = tool_call.get("id", "")
                                tool_name = tool_call.get("function", {}).get(
                                    "name", ""
                                )
                                tool_arguments = tool_call.get("function", {}).get(
                                    "arguments", ""
                                )

                                tool_result = None
                                tool_result_files = None
                                for result in results:
                                    if tool_call_id == result.get("tool_call_id", ""):
                                        tool_result = result.get("content", None)
                                        tool_result_files = result.get("files", None)
                                        break

                                if tool_result:
                                    tool_calls_display_content = f'{tool_calls_display_content}\n<details type="tool_calls" done="true" id="{tool_call_id}" name="{tool_name}" arguments="{html.escape(json.dumps(tool_arguments))}" result="{html.escape(json.dumps(tool_result))}" files="{html.escape(json.dumps(tool_result_files)) if tool_result_files else ""}">\n<summary>Tool Executed</summary>\n</details>\n'
                                else:
                                    tool_calls_display_content = f'{tool_calls_display_content}\n<details type="tool_calls" done="false" id="{tool_call_id}" name="{tool_name}" arguments="{html.escape(json.dumps(tool_arguments))}">\n<summary>Executing...</summary>\n</details>'

                            if not raw:
                                content = f"{content}\n{tool_calls_display_content}\n\n"
                        else:
                            tool_calls_display_content = ""

                            for tool_call in tool_calls:
                                tool_call_id = tool_call.get("id", "")
                                tool_name = tool_call.get("function", {}).get(
                                    "name", ""
                                )
                                tool_arguments = tool_call.get("function", {}).get(
                                    "arguments", ""
                                )

                                tool_calls_display_content = f'{tool_calls_display_content}\n<details type="tool_calls" done="false" id="{tool_call_id}" name="{tool_name}" arguments="{html.escape(json.dumps(tool_arguments))}">\n<summary>Executing...</summary>\n</details>'

                            if not raw:
                                content = f"{content}\n{tool_calls_display_content}\n\n"

                    elif block["type"] == "reasoning":
                        reasoning_display_content = "\n".join(
                            (f"> {line}" if not line.startswith(">") else line)
                            for line in block["content"].splitlines()
                        )

                        reasoning_duration = block.get("duration", None)

                        if reasoning_duration is not None:
                            if raw:
                                content = f'{content}\n<{block["start_tag"]}>{block["content"]}<{block["end_tag"]}>\n'
                            else:
                                content = f'{content}\n<details type="reasoning" done="true" duration="{reasoning_duration}">\n<summary>Thought for {reasoning_duration} seconds</summary>\n{reasoning_display_content}\n</details>\n'
                        else:
                            if raw:
                                content = f'{content}\n<{block["start_tag"]}>{block["content"]}<{block["end_tag"]}>\n'
                            else:
                                content = f'{content}\n<details type="reasoning" done="false">\n<summary>Thinking…</summary>\n{reasoning_display_content}\n</details>\n'

                    elif block["type"] == "code_interpreter":
                        attributes = block.get("attributes", {})
                        output = block.get("output", None)
                        lang = attributes.get("lang", "")

                        content_stripped, original_whitespace = (
                            split_content_and_whitespace(content)
                        )
                        if is_opening_code_block(content_stripped):
                            # Remove trailing backticks that would open a new block
                            content = (
                                content_stripped.rstrip("`").rstrip()
                                + original_whitespace
                            )
                        else:
                            # Keep content as is - either closing backticks or no backticks
                            content = content_stripped + original_whitespace

                        if output:
                            output = html.escape(json.dumps(output))

                            if raw:
                                content = f'{content}\n<code_interpreter type="code" lang="{lang}">\n{block["content"]}\n</code_interpreter>\n```output\n{output}\n```\n'
                            else:
                                content = f'{content}\n<details type="code_interpreter" done="true" output="{output}">\n<summary>Analyzed</summary>\n```{lang}\n{block["content"]}\n```\n</details>\n'
                        else:
                            if raw:
                                content = f'{content}\n<code_interpreter type="code" lang="{lang}">\n{block["content"]}\n</code_interpreter>\n'
                            else:
                                content = f'{content}\n<details type="code_interpreter" done="false">\n<summary>Analyzing...</summary>\n```{lang}\n{block["content"]}\n```\n</details>\n'

                    else:
                        block_content = str(block["content"]).strip()
                        content = f"{content}{block['type']}: {block_content}\n"

                return content.strip()

            def convert_content_blocks_to_messages(content_blocks):
                messages = []

                temp_blocks = []
                for idx, block in enumerate(content_blocks):
                    if block["type"] == "tool_calls":
                        messages.append(
                            {
                                "role": "assistant",
                                "content": serialize_content_blocks(temp_blocks),
                                "tool_calls": block.get("content"),
                            }
                        )

                        results = block.get("results", [])

                        for result in results:
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": result["tool_call_id"],
                                    "content": result["content"],
                                }
                            )
                        temp_blocks = []
                    else:
                        temp_blocks.append(block)

                if temp_blocks:
                    content = serialize_content_blocks(temp_blocks)
                    if content:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": content,
                            }
                        )

                return messages

            def tag_content_handler(content_type, tags, content, content_blocks):
                end_flag = False

                def extract_attributes(tag_content):
                    """Extract attributes from a tag if they exist."""
                    attributes = {}
                    if not tag_content:  # Ensure tag_content is not None
                        return attributes
                    # Match attributes in the format: key="value" (ignores single quotes for simplicity)
                    matches = re.findall(r'(\w+)\s*=\s*"([^"]+)"', tag_content)
                    for key, value in matches:
                        attributes[key] = value
                    return attributes

                if content_blocks[-1]["type"] == "text":
                    for start_tag, end_tag in tags:
                        # Match start tag e.g., <tag> or <tag attr="value">
                        start_tag_pattern = rf"<{re.escape(start_tag)}(\s.*?)?>"
                        match = re.search(start_tag_pattern, content)
                        if match:
                            attr_content = (
                                match.group(1) if match.group(1) else ""
                            )  # Ensure it's not None
                            attributes = extract_attributes(
                                attr_content
                            )  # Extract attributes safely

                            # Capture everything before and after the matched tag
                            before_tag = content[
                                : match.start()
                            ]  # Content before opening tag
                            after_tag = content[
                                match.end() :
                            ]  # Content after opening tag

                            # Remove the start tag and after from the currently handling text block
                            content_blocks[-1]["content"] = content_blocks[-1][
                                "content"
                            ].replace(match.group(0) + after_tag, "")

                            if before_tag:
                                content_blocks[-1]["content"] = before_tag

                            if not content_blocks[-1]["content"]:
                                content_blocks.pop()

                            # Append the new block
                            content_blocks.append(
                                {
                                    "type": content_type,
                                    "start_tag": start_tag,
                                    "end_tag": end_tag,
                                    "attributes": attributes,
                                    "content": "",
                                    "started_at": time.time(),
                                }
                            )

                            if after_tag:
                                content_blocks[-1]["content"] = after_tag

                            break
                elif content_blocks[-1]["type"] == content_type:
                    start_tag = content_blocks[-1]["start_tag"]
                    end_tag = content_blocks[-1]["end_tag"]
                    # Match end tag e.g., </tag>
                    end_tag_pattern = rf"<{re.escape(end_tag)}>"

                    # Check if the content has the end tag
                    if re.search(end_tag_pattern, content):
                        end_flag = True

                        block_content = content_blocks[-1]["content"]
                        # Strip start and end tags from the content
                        start_tag_pattern = rf"<{re.escape(start_tag)}(.*?)>"
                        block_content = re.sub(
                            start_tag_pattern, "", block_content
                        ).strip()

                        end_tag_regex = re.compile(end_tag_pattern, re.DOTALL)
                        split_content = end_tag_regex.split(block_content, maxsplit=1)

                        # Content inside the tag
                        block_content = (
                            split_content[0].strip() if split_content else ""
                        )

                        # Leftover content (everything after `</tag>`)
                        leftover_content = (
                            split_content[1].strip() if len(split_content) > 1 else ""
                        )

                        if block_content:
                            content_blocks[-1]["content"] = block_content
                            content_blocks[-1]["ended_at"] = time.time()
                            content_blocks[-1]["duration"] = int(
                                content_blocks[-1]["ended_at"]
                                - content_blocks[-1]["started_at"]
                            )

                            # Reset the content_blocks by appending a new text block
                            if content_type != "code_interpreter":
                                if leftover_content:

                                    content_blocks.append(
                                        {
                                            "type": "text",
                                            "content": leftover_content,
                                        }
                                    )
                                else:
                                    content_blocks.append(
                                        {
                                            "type": "text",
                                            "content": "",
                                        }
                                    )

                        else:
                            # Remove the block if content is empty
                            content_blocks.pop()

                            if leftover_content:
                                content_blocks.append(
                                    {
                                        "type": "text",
                                        "content": leftover_content,
                                    }
                                )
                            else:
                                content_blocks.append(
                                    {
                                        "type": "text",
                                        "content": "",
                                    }
                                )

                        # Clean processed content
                        content = re.sub(
                            rf"<{re.escape(start_tag)}(.*?)>(.|\n)*?<{re.escape(end_tag)}>",
                            "",
                            content,
                            flags=re.DOTALL,
                        )

                return content, content_blocks, end_flag

            message = Chats.get_message_by_id_and_message_id(
                metadata["chat_id"], metadata["message_id"]
            )

            tool_calls = []

            last_assistant_message = None
            try:
                if form_data["messages"][-1]["role"] == "assistant":
                    last_assistant_message = get_last_assistant_message(
                        form_data["messages"]
                    )
            except Exception as e:
                pass

            content = (
                message.get("content", "")
                if message
                else last_assistant_message if last_assistant_message else ""
            )

            usage_data = None
            content_blocks = [
                {
                    "type": "text",
                    "content": content,
                }
            ]

            # We might want to disable this by default
            DETECT_REASONING = True
            DETECT_SOLUTION = True
            DETECT_CODE_INTERPRETER = metadata.get("features", {}).get(
                "code_interpreter", False
            )

            reasoning_tags = [
                ("think", "/think"),
                ("thinking", "/thinking"),
                ("reason", "/reason"),
                ("reasoning", "/reasoning"),
                ("thought", "/thought"),
                ("Thought", "/Thought"),
                ("|begin_of_thought|", "|end_of_thought|"),
            ]

            code_interpreter_tags = [("code_interpreter", "/code_interpreter")]

            solution_tags = [("|begin_of_solution|", "|end_of_solution|")]

            try:
                for event in events:
                    await event_emitter(
                        {
                            "type": "chat:completion",
                            "data": event,
                        }
                    )

                    # Save message in the database
                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        metadata["message_id"],
                        {
                            **event,
                        },
                    )
                    # Update normalized table (for event data)
                    try:
                        if "content" in event:
                            ChatMessages.update_message(
                                metadata["message_id"],
                                content_text=event["content"],
                                skip_metrics_rollup=ENABLE_REALTIME_CHAT_SAVE,
                            )
                        # Persist sources if present in event
                        if "sources" in event:
                            ChatMessages.set_sources(
                                metadata["message_id"],
                                event["sources"]
                            )
                    except Exception as e:
                        log.debug(f"Failed to update normalized message from event: {e}")

                async def stream_body_handler(response):
                    nonlocal content
                    nonlocal content_blocks
                    nonlocal usage_data
                    usage_data = None

                    response_tool_calls = []

                    def persist_realtime_content(serialized_content=None):
                        if not ENABLE_REALTIME_CHAT_SAVE:
                            return

                        if serialized_content is None:
                            serialized_content = serialize_content_blocks(content_blocks)

                        # Save message in the database
                        Chats.upsert_message_to_chat_by_id_and_message_id(
                            metadata["chat_id"],
                            metadata["message_id"],
                            {
                                "content": serialized_content,
                            },
                        )
                        # Update normalized table (usage will be saved when stream completes)
                        try:
                            ChatMessages.update_message(
                                metadata["message_id"],
                                content_text=serialized_content,
                                skip_metrics_rollup=ENABLE_REALTIME_CHAT_SAVE,
                            )
                        except Exception as e:
                            log.debug(
                                f"Failed to update normalized message content (realtime): {e}"
                            )

                    async for line in response.body_iterator:
                        line = line.decode("utf-8") if isinstance(line, bytes) else line
                        data = line

                        # Skip empty lines
                        if not data.strip():
                            continue

                        # "data:" is the prefix for each event
                        if not data.startswith("data:"):
                            continue

                        # Remove the prefix
                        data = data[len("data:") :].strip()

                        try:
                            data = json.loads(data)

                            data, _ = await process_filter_functions(
                                request=request,
                                filter_functions=filter_functions,
                                filter_type="stream",
                                form_data=data,
                                extra_params=extra_params,
                            )

                            if data:
                                if "event" in data:
                                    await event_emitter(data.get("event", {}))

                                if "selected_model_id" in data:
                                    model_id = data["selected_model_id"]
                                    Chats.upsert_message_to_chat_by_id_and_message_id(
                                        metadata["chat_id"],
                                        metadata["message_id"],
                                        {
                                            "selectedModelId": model_id,
                                        },
                                    )
                                    # Update normalized table
                                    try:
                                        ChatMessages.update_message(
                                            metadata["message_id"],
                                            meta={"selectedModelId": model_id},
                                            skip_metrics_rollup=ENABLE_REALTIME_CHAT_SAVE,
                                        )
                                    except Exception as e:
                                        log.debug(f"Failed to update normalized message selectedModelId: {e}")
                                else:
                                    choices = data.get("choices", [])
                                    if not choices:
                                        error = data.get("error", {})
                                        if error:
                                            await event_emitter(
                                                {
                                                    "type": "chat:completion",
                                                    "data": {
                                                        "error": error,
                                                    },
                                                }
                                            )
                                        usage = data.get("usage", {})
                                        if usage:
                                            usage_data = usage  # Store for later save
                                            await event_emitter(
                                                {
                                                    "type": "chat:completion",
                                                    "data": {
                                                        "usage": usage,
                                                    },
                                                }
                                            )
                                        continue

                                    delta = choices[0].get("delta", {})
                                    delta_tool_calls = delta.get("tool_calls", None)

                                    if delta_tool_calls:
                                        for delta_tool_call in delta_tool_calls:
                                            tool_call_index = delta_tool_call.get(
                                                "index"
                                            )

                                            if tool_call_index is not None:
                                                # Check if the tool call already exists
                                                current_response_tool_call = None
                                                for (
                                                    response_tool_call
                                                ) in response_tool_calls:
                                                    if (
                                                        response_tool_call.get("index")
                                                        == tool_call_index
                                                    ):
                                                        current_response_tool_call = (
                                                            response_tool_call
                                                        )
                                                        break

                                                if current_response_tool_call is None:
                                                    # Add the new tool call
                                                    response_tool_calls.append(
                                                        delta_tool_call
                                                    )
                                                else:
                                                    # Update the existing tool call
                                                    delta_name = delta_tool_call.get(
                                                        "function", {}
                                                    ).get("name")
                                                    delta_arguments = (
                                                        delta_tool_call.get(
                                                            "function", {}
                                                        ).get("arguments")
                                                    )

                                                    if delta_name:
                                                        current_response_tool_call[
                                                            "function"
                                                        ]["name"] += delta_name

                                                    if delta_arguments:
                                                        current_response_tool_call[
                                                            "function"
                                                        ][
                                                            "arguments"
                                                        ] += delta_arguments

                                    value = delta.get("content")

                                    reasoning_content = delta.get(
                                        "reasoning_content"
                                    ) or delta.get("reasoning")
                                    if reasoning_content:
                                        if (
                                            not content_blocks
                                            or content_blocks[-1]["type"] != "reasoning"
                                        ):
                                            reasoning_block = {
                                                "type": "reasoning",
                                                "start_tag": "think",
                                                "end_tag": "/think",
                                                "attributes": {
                                                    "type": "reasoning_content"
                                                },
                                                "content": "",
                                                "started_at": time.time(),
                                            }
                                            content_blocks.append(reasoning_block)
                                        else:
                                            reasoning_block = content_blocks[-1]

                                        reasoning_block["content"] += reasoning_content

                                        data = {
                                            "content": serialize_content_blocks(
                                                content_blocks
                                            )
                                        }

                                        persist_realtime_content(data["content"])

                                    if value:
                                        if (
                                            content_blocks
                                            and content_blocks[-1]["type"]
                                            == "reasoning"
                                            and content_blocks[-1]
                                            .get("attributes", {})
                                            .get("type")
                                            == "reasoning_content"
                                        ):
                                            reasoning_block = content_blocks[-1]
                                            reasoning_block["ended_at"] = time.time()
                                            reasoning_block["duration"] = int(
                                                reasoning_block["ended_at"]
                                                - reasoning_block["started_at"]
                                            )

                                            content_blocks.append(
                                                {
                                                    "type": "text",
                                                    "content": "",
                                                }
                                            )

                                        content = f"{content}{value}"
                                        if not content_blocks:
                                            content_blocks.append(
                                                {
                                                    "type": "text",
                                                    "content": "",
                                                }
                                            )

                                        content_blocks[-1]["content"] = (
                                            content_blocks[-1]["content"] + value
                                        )

                                        if DETECT_REASONING:
                                            content, content_blocks, _ = (
                                                tag_content_handler(
                                                    "reasoning",
                                                    reasoning_tags,
                                                    content,
                                                    content_blocks,
                                                )
                                            )

                                        if DETECT_CODE_INTERPRETER:
                                            content, content_blocks, end = (
                                                tag_content_handler(
                                                    "code_interpreter",
                                                    code_interpreter_tags,
                                                    content,
                                                    content_blocks,
                                                )
                                            )

                                            if end:
                                                break

                                        if DETECT_SOLUTION:
                                            content, content_blocks, _ = (
                                                tag_content_handler(
                                                    "solution",
                                                    solution_tags,
                                                    content,
                                                    content_blocks,
                                                )
                                            )

                                        serialized_content = serialize_content_blocks(
                                            content_blocks
                                        )

                                        if ENABLE_REALTIME_CHAT_SAVE:
                                            persist_realtime_content(serialized_content)
                                        else:
                                            data = {
                                                "content": serialized_content,
                                            }

                                await event_emitter(
                                    {
                                        "type": "chat:completion",
                                        "data": data,
                                    }
                                )
                        except Exception as e:
                            done = "data: [DONE]" in line
                            if done:
                                pass
                            else:
                                log.debug("Error: ", e)
                                continue

                    if content_blocks:
                        # Clean up the last text block
                        if content_blocks[-1]["type"] == "text":
                            content_blocks[-1]["content"] = content_blocks[-1][
                                "content"
                            ].strip()

                            if not content_blocks[-1]["content"]:
                                content_blocks.pop()

                                if not content_blocks:
                                    content_blocks.append(
                                        {
                                            "type": "text",
                                            "content": "",
                                        }
                                    )

                    if response_tool_calls:
                        tool_calls.append(response_tool_calls)

                    if response.background:
                        await response.background()

                await stream_body_handler(response)

                MAX_TOOL_CALL_RETRIES = 10
                tool_call_retries = 0

                while len(tool_calls) > 0 and tool_call_retries < MAX_TOOL_CALL_RETRIES:
                    tool_call_retries += 1

                    response_tool_calls = tool_calls.pop(0)

                    content_blocks.append(
                        {
                            "type": "tool_calls",
                            "content": response_tool_calls,
                        }
                    )

                    await event_emitter(
                        {
                            "type": "chat:completion",
                            "data": {
                                "content": serialize_content_blocks(content_blocks),
                            },
                        }
                    )

                    tools = metadata.get("tools", {})

                    results = []
                    for tool_call in response_tool_calls:
                        tool_call_id = tool_call.get("id", "")
                        tool_name = tool_call.get("function", {}).get("name", "")

                        tool_function_params = {}
                        try:
                            # json.loads cannot be used because some models do not produce valid JSON
                            tool_function_params = ast.literal_eval(
                                tool_call.get("function", {}).get("arguments", "{}")
                            )
                        except Exception as e:
                            log.debug(e)
                            # Fallback to JSON parsing
                            try:
                                tool_function_params = json.loads(
                                    tool_call.get("function", {}).get("arguments", "{}")
                                )
                            except Exception as e:
                                log.debug(
                                    f"Error parsing tool call arguments: {tool_call.get('function', {}).get('arguments', '{}')}"
                                )

                        tool_result = None

                        if tool_name in tools:
                            tool = tools[tool_name]
                            spec = tool.get("spec", {})

                            try:
                                allowed_params = (
                                    spec.get("parameters", {})
                                    .get("properties", {})
                                    .keys()
                                )

                                tool_function_params = {
                                    k: v
                                    for k, v in tool_function_params.items()
                                    if k in allowed_params
                                }

                                if tool.get("direct", False):
                                    tool_result = await event_caller(
                                        {
                                            "type": "execute:tool",
                                            "data": {
                                                "id": str(uuid4()),
                                                "name": tool_name,
                                                "params": tool_function_params,
                                                "server": tool.get("server", {}),
                                                "session_id": metadata.get(
                                                    "session_id", None
                                                ),
                                            },
                                        }
                                    )

                                else:
                                    tool_function = tool["callable"]
                                    tool_result = await tool_function(
                                        **tool_function_params
                                    )

                            except Exception as e:
                                tool_result = str(e)

                        tool_result_files = []
                        if isinstance(tool_result, list):
                            for item in tool_result:
                                # check if string
                                if isinstance(item, str) and item.startswith("data:"):
                                    tool_result_files.append(item)
                                    tool_result.remove(item)

                        if isinstance(tool_result, dict) or isinstance(
                            tool_result, list
                        ):
                            tool_result = json.dumps(tool_result, indent=2)

                        results.append(
                            {
                                "tool_call_id": tool_call_id,
                                "content": tool_result,
                                **(
                                    {"files": tool_result_files}
                                    if tool_result_files
                                    else {}
                                ),
                            }
                        )

                    content_blocks[-1]["results"] = results

                    content_blocks.append(
                        {
                            "type": "text",
                            "content": "",
                        }
                    )

                    await event_emitter(
                        {
                            "type": "chat:completion",
                            "data": {
                                "content": serialize_content_blocks(content_blocks),
                            },
                        }
                    )

                    try:
                        res = await generate_chat_completion(
                            request,
                            {
                                "model": model_id,
                                "stream": True,
                                "tools": form_data["tools"],
                                "messages": [
                                    *form_data["messages"],
                                    *convert_content_blocks_to_messages(content_blocks),
                                ],
                            },
                            user,
                        )

                        if isinstance(res, StreamingResponse):
                            await stream_body_handler(res)
                        else:
                            break
                    except Exception as e:
                        log.debug(e)
                        break

                if DETECT_CODE_INTERPRETER:
                    MAX_RETRIES = 5
                    retries = 0

                    while (
                        content_blocks[-1]["type"] == "code_interpreter"
                        and retries < MAX_RETRIES
                    ):
                        await event_emitter(
                            {
                                "type": "chat:completion",
                                "data": {
                                    "content": serialize_content_blocks(content_blocks),
                                },
                            }
                        )

                        retries += 1
                        log.debug(f"Attempt count: {retries}")

                        output = ""
                        try:
                            if content_blocks[-1]["attributes"].get("type") == "code":
                                code = content_blocks[-1]["content"]

                                if (
                                    request.app.state.config.CODE_INTERPRETER_ENGINE
                                    == "pyodide"
                                ):
                                    output = await event_caller(
                                        {
                                            "type": "execute:python",
                                            "data": {
                                                "id": str(uuid4()),
                                                "code": code,
                                                "session_id": metadata.get(
                                                    "session_id", None
                                                ),
                                            },
                                        }
                                    )
                                elif (
                                    request.app.state.config.CODE_INTERPRETER_ENGINE
                                    == "jupyter"
                                ):
                                    output = await execute_code_jupyter(
                                        request.app.state.config.CODE_INTERPRETER_JUPYTER_URL,
                                        code,
                                        (
                                            request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_TOKEN
                                            if request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH
                                            == "token"
                                            else None
                                        ),
                                        (
                                            request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD
                                            if request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH
                                            == "password"
                                            else None
                                        ),
                                        request.app.state.config.CODE_INTERPRETER_JUPYTER_TIMEOUT,
                                    )
                                else:
                                    output = {
                                        "stdout": "Code interpreter engine not configured."
                                    }

                                log.debug(f"Code interpreter output: {output}")

                                if isinstance(output, dict):
                                    stdout = output.get("stdout", "")

                                    if isinstance(stdout, str):
                                        stdoutLines = stdout.split("\n")
                                        for idx, line in enumerate(stdoutLines):
                                            if "data:image/png;base64" in line:
                                                id = str(uuid4())

                                                # ensure the path exists
                                                os.makedirs(
                                                    os.path.join(CACHE_DIR, "images"),
                                                    exist_ok=True,
                                                )

                                                image_path = os.path.join(
                                                    CACHE_DIR,
                                                    f"images/{id}.png",
                                                )

                                                with open(image_path, "wb") as f:
                                                    f.write(
                                                        base64.b64decode(
                                                            line.split(",")[1]
                                                        )
                                                    )

                                                stdoutLines[idx] = (
                                                    f"![Output Image {idx}](/cache/images/{id}.png)"
                                                )

                                        output["stdout"] = "\n".join(stdoutLines)

                                    result = output.get("result", "")

                                    if isinstance(result, str):
                                        resultLines = result.split("\n")
                                        for idx, line in enumerate(resultLines):
                                            if "data:image/png;base64" in line:
                                                id = str(uuid4())

                                                # ensure the path exists
                                                os.makedirs(
                                                    os.path.join(CACHE_DIR, "images"),
                                                    exist_ok=True,
                                                )

                                                image_path = os.path.join(
                                                    CACHE_DIR,
                                                    f"images/{id}.png",
                                                )

                                                with open(image_path, "wb") as f:
                                                    f.write(
                                                        base64.b64decode(
                                                            line.split(",")[1]
                                                        )
                                                    )

                                                resultLines[idx] = (
                                                    f"![Output Image {idx}](/cache/images/{id}.png)"
                                                )

                                        output["result"] = "\n".join(resultLines)
                        except Exception as e:
                            output = str(e)

                        content_blocks[-1]["output"] = output

                        content_blocks.append(
                            {
                                "type": "text",
                                "content": "",
                            }
                        )

                        await event_emitter(
                            {
                                "type": "chat:completion",
                                "data": {
                                    "content": serialize_content_blocks(content_blocks),
                                },
                            }
                        )

                        try:
                            res = await generate_chat_completion(
                                request,
                                {
                                    "model": model_id,
                                    "stream": True,
                                    "messages": [
                                        *form_data["messages"],
                                        {
                                            "role": "assistant",
                                            "content": serialize_content_blocks(
                                                content_blocks, raw=True
                                            ),
                                        },
                                    ],
                                },
                                user,
                            )

                            if isinstance(res, StreamingResponse):
                                await stream_body_handler(res)
                            else:
                                break
                        except Exception as e:
                            log.debug(e)
                            break

                title = Chats.get_chat_title_by_id(metadata["chat_id"])
                data = {
                    "done": True,
                    "content": serialize_content_blocks(content_blocks),
                    "title": title,
                }

                if ENABLE_REALTIME_CHAT_SAVE:
                    # Late-stage updates: persist usage once and update active_message_id
                    try:
                        if usage_data:
                            ChatMessages.update_message(
                                metadata["message_id"],
                                usage=usage_data,
                            )
                        Chats.update_chat_active_and_root_message_ids(
                            metadata["chat_id"], active_message_id=metadata["message_id"]
                        )
                    except Exception as e:
                        log.debug(f"Failed to finalize realtime message content: {e}")
                else:
                    # Save message in the database
                    serialized_content = serialize_content_blocks(content_blocks)
                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        metadata["message_id"],
                        {
                            "content": serialized_content,
                        },
                    )
                    # Update normalized table with content and usage
                    try:
                        ChatMessages.update_message(
                            metadata["message_id"],
                            content_text=serialized_content,
                            usage=usage_data
                        )
                        # Update active_message_id
                        Chats.update_chat_active_and_root_message_ids(metadata["chat_id"], active_message_id=metadata["message_id"])
                    except Exception as e:
                        log.debug(f"Failed to update normalized message content (final): {e}")

                # Send a webhook notification if the user is not active
                if get_active_status_by_user_id(user.id) is None:
                    webhook_url = Users.get_user_webhook_url_by_id(user.id)
                    if webhook_url:
                        post_webhook(
                            request.app.state.WEBUI_NAME,
                            webhook_url,
                            f"{title} - {request.app.state.config.WEBUI_URL}/c/{metadata['chat_id']}\n\n{content}",
                            {
                                "action": "chat",
                                "message": content,
                                "title": title,
                                "url": f"{request.app.state.config.WEBUI_URL}/c/{metadata['chat_id']}",
                            },
                        )

                await event_emitter(
                    {
                        "type": "chat:completion",
                        "data": data,
                    }
                )

                await background_tasks_handler()
            except asyncio.CancelledError:
                log.warning("Task was cancelled!")
                await event_emitter({"type": "task-cancelled"})

                if not ENABLE_REALTIME_CHAT_SAVE:
                    # Save message in the database
                    serialized_content = serialize_content_blocks(content_blocks)
                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        metadata["message_id"],
                        {
                            "content": serialized_content,
                        },
                    )
                    # Update normalized table
                    try:
                        ChatMessages.update_message(
                            metadata["message_id"],
                            content_text=serialized_content
                        )
                    except Exception as e:
                        log.debug(f"Failed to update normalized message content (cancelled): {e}")

            if response.background is not None:
                await response.background()

        # background_tasks.add_task(post_response_handler, response, events)
        task_id, _ = create_task(
            post_response_handler(response, events), id=metadata["chat_id"]
        )
        return {"status": True, "task_id": task_id}

    else:
        # Fallback to the original response
        async def stream_wrapper(original_generator, events):
            def wrap_item(item):
                return f"data: {item}\n\n"

            for event in events:
                event, _ = await process_filter_functions(
                    request=request,
                    filter_functions=filter_functions,
                    filter_type="stream",
                    form_data=event,
                    extra_params=extra_params,
                )

                if event:
                    yield wrap_item(json.dumps(event))

            async for data in original_generator:
                data, _ = await process_filter_functions(
                    request=request,
                    filter_functions=filter_functions,
                    filter_type="stream",
                    form_data=data,
                    extra_params=extra_params,
                )

                if data:
                    yield data

        return StreamingResponse(
            stream_wrapper(response.body_iterator, events),
            headers=dict(response.headers),
            background=response.background,
        )
