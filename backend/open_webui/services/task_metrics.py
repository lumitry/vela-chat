import hashlib
import json
import logging
import time
import uuid
from typing import Optional, Tuple

from open_webui.internal.db import get_db
from open_webui.models.tasks import TaskPromptTemplate, TaskGeneration
from open_webui.models.chat_messages import extract_tokens_from_usage, extract_cost_from_usage
from open_webui.models.chats import Chat
from open_webui.constants import TASKS
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS.get("MODELS", logging.INFO))


def normalize_template(template: str) -> str:
    """
    Normalize a template string for deduplication.
    - Strip trailing whitespace
    - Normalize line endings to \n
    - Collapse multiple spaces to single space (but preserve structure)
    - Leave {{}} placeholders intact
    """
    # Normalize line endings
    template = template.replace('\r\n', '\n').replace('\r', '\n')
    
    # Strip trailing whitespace from each line, but preserve structure
    lines = template.split('\n')
    normalized_lines = [line.rstrip() for line in lines]
    template = '\n'.join(normalized_lines)
    
    # Strip overall leading/trailing whitespace
    template = template.strip()
    
    return template


def compute_template_hash(template: str) -> str:
    """Compute SHA256 hash of normalized template"""
    normalized = normalize_template(template)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def get_or_create_task_prompt_template(
    task_type: str,
    template_string: str,
    source: str = "default"
) -> str:
    """
    Get or create a task prompt template record.
    Returns the template ID.
    """
    template_hash = compute_template_hash(template_string)
    normalized_template = normalize_template(template_string)
    
    with get_db() as db:
        # Try to find existing template
        existing = db.query(TaskPromptTemplate).filter_by(
            task_type=task_type,
            template_hash=template_hash
        ).first()
        
        if existing:
            return existing.id
        
        # Create new template
        template_id = str(uuid.uuid4())
        ts = int(time.time())
        
        new_template = TaskPromptTemplate(
            id=template_id,
            task_type=task_type,
            template=normalized_template,
            template_hash=template_hash,
            source=source,
            version=1,
            created_at=ts,
            updated_at=ts,
        )
        
        db.add(new_template)
        db.commit()
        
        log.debug(f"Created new task prompt template: {template_id} for task_type={task_type}, source={source}")
        return template_id


def determine_task_model_type(task_model_id: str, models: dict) -> str:
    """
    Determine if task model is internal (ollama) or external.
    Returns 'internal' or 'external'.
    """
    model_info = models.get(task_model_id, {})
    owned_by = model_info.get("owned_by", "")
    
    if owned_by == "ollama":
        return "internal"
    else:
        return "external"


def determine_is_success(
    task_type: str,
    response_text: Optional[str],
    error: Optional[dict] = None
) -> bool:
    """
    Determine if a task generation was successful based on task type and response.
    """
    if error is not None:
        return False
    
    if not response_text or not response_text.strip():
        return False
    
    try:
        if task_type == str(TASKS.TITLE_GENERATION):
            # Try to parse JSON and check for non-empty title
            bracket_start = response_text.find("{")
            bracket_end = response_text.rfind("}") + 1
            if bracket_start == -1 or bracket_end == 0:
                return False
            json_str = response_text[bracket_start:bracket_end]
            parsed = json.loads(json_str)
            title = parsed.get("title", "")
            return bool(title and title.strip())
        
        elif task_type == str(TASKS.TAGS_GENERATION):
            # Try to parse JSON and check for non-empty tags array
            bracket_start = response_text.find("{")
            bracket_end = response_text.rfind("}") + 1
            if bracket_start == -1 or bracket_end == 0:
                return False
            json_str = response_text[bracket_start:bracket_end]
            parsed = json.loads(json_str)
            tags = parsed.get("tags", [])
            return bool(isinstance(tags, list) and len(tags) > 0)
        
        elif task_type == str(TASKS.IMAGE_PROMPT_GENERATION):
            # Try to parse JSON and check for non-empty prompt
            bracket_start = response_text.find("{")
            bracket_end = response_text.rfind("}") + 1
            if bracket_start == -1 or bracket_end == 0:
                return False
            json_str = response_text[bracket_start:bracket_end]
            parsed = json.loads(json_str)
            prompt = parsed.get("prompt", "")
            return bool(prompt and prompt.strip())
        
        elif task_type == str(TASKS.QUERY_GENERATION):
            # Try to parse JSON or plain text, check for at least one non-empty query
            bracket_start = response_text.find("{")
            bracket_end = response_text.rfind("}") + 1
            if bracket_start != -1 and bracket_end > 0:
                try:
                    json_str = response_text[bracket_start:bracket_end]
                    parsed = json.loads(json_str)
                    queries = parsed.get("queries", [])
                    if isinstance(queries, list):
                        return bool(any(q and q.strip() for q in queries))
                except:
                    pass
            
            # Fallback: check if response_text itself is non-empty
            return bool(response_text.strip())
        
        else:
            # Default: if we got a response, consider it successful
            return True
    
    except Exception as e:
        log.debug(f"Error determining is_success for task_type={task_type}: {e}")
        return False


def record_task_generation(
    task_type: str,
    chat_id: str,
    message_id: str,
    user_id: str,
    task_model_id: str,
    models: dict,
    template_string: str,
    template_source: str,
    response_text: Optional[str],
    usage: Optional[dict] = None,
    error: Optional[dict] = None,
) -> Optional[str]:
    """
    Record a task generation in the database.
    
    Args:
        task_type: The type of task (from TASKS enum)
        chat_id: ID of the chat
        message_id: ID of the message associated with this task
        user_id: ID of the user
        task_model_id: ID of the model used for the task
        models: Dictionary of model info (to determine owned_by)
        template_string: The prompt template string used
        template_source: Source of template ('default' or 'config')
        response_text: The response text from the model
        usage: Usage information from the model response
        error: Error information if generation failed
    
    Returns:
        The task_generation ID if successful, None otherwise
    """
    try:
        # Get or create prompt template
        prompt_template_id = get_or_create_task_prompt_template(
            task_type=task_type,
            template_string=template_string,
            source=template_source
        )
        
        # Determine task model type
        task_model_type = determine_task_model_type(task_model_id, models)
        
        # Extract usage information
        cost = extract_cost_from_usage(usage)
        input_tokens, output_tokens, reasoning_tokens = extract_tokens_from_usage(usage)
        
        # Determine success
        is_success = determine_is_success(task_type, response_text, error)
        
        # Create task generation record
        generation_id = str(uuid.uuid4())
        ts = int(time.time())
        
        with get_db() as db:
            # Verify chat exists and get user_id if not provided
            chat = db.query(Chat).filter_by(id=chat_id).first()
            if not chat:
                log.warning(f"Chat {chat_id} not found, skipping task generation record")
                return None
            
            # Use chat.user_id if user_id not provided (shouldn't happen, but be safe)
            actual_user_id = user_id or chat.user_id
            if not actual_user_id:
                log.warning(f"No user_id for chat {chat_id}, skipping task generation record")
                return None
            
            task_gen = TaskGeneration(
                id=generation_id,
                chat_id=chat_id,
                message_id=message_id,
                user_id=actual_user_id,
                task_type=task_type,
                prompt_template_id=prompt_template_id,
                model_id=task_model_id,
                task_model_type=task_model_type,
                response_text=response_text,
                usage=usage,
                cost=cost,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                reasoning_tokens=reasoning_tokens,
                is_success=is_success,
                error=error,
                created_at=ts,
                updated_at=ts,
            )
            
            db.add(task_gen)
            db.commit()
            
            log.debug(
                f"Recorded task generation: {generation_id} "
                f"(task_type={task_type}, model={task_model_id}, "
                f"success={is_success}, tokens={input_tokens or 0}+{output_tokens or 0})"
            )
            
            return generation_id
    
    except Exception as e:
        log.error(f"Error recording task generation: {e}", exc_info=True)
        return None

