import os

from fastapi import APIRouter, Depends, Request
from urllib.parse import urlparse

from talk2dom.core import call_selector_llm, retry
from talk2dom.db.cache import get_cached_locator, save_locator
from talk2dom.db.session import Session, get_db
from talk2dom.api.schemas import LocatorRequest, LocatorResponse
from talk2dom.api.utils.validator import SelectorValidator
from talk2dom.api.utils.html_cleaner import (
    clean_html,
    clean_html_keep_structure_only,
)
from loguru import logger
from talk2dom.db.models import User
from talk2dom.api.deps import (
    get_api_key_user,
    track_api_usage,
    get_api_key_id,
    get_current_project_id,
    get_current_user,
    playground_track_api_usage,
)
from talk2dom.api.limiter import limiter


router = APIRouter()  #

MODEL_NAME = os.environ.get("TALK2DOM_MODEL_NAME")
PROVIDER_NAME = os.environ.get("TALK2DOM_MODEL_PROVIDER_NAME")


@router.post("/locator", response_model=LocatorResponse)
@limiter.limit("60/minute")
@retry()
@track_api_usage()
def locate(
    req: LocatorRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_api_key_user),
    api_key_id: str = Depends(get_api_key_id),
    project_id: str = Depends(get_current_project_id),
):
    html = req.html
    if not html:
        raise Exception("html is empty")
    try:
        cleaned_html = clean_html(html)
        structure_html = clean_html_keep_structure_only(cleaned_html)
        if cleaned_html is None:
            raise Exception(
                "make sure the html is valid and has meaningful information"
            )
    except Exception as err:
        logger.error(f"Failed to clean html: {err}")
        raise
    verifier = SelectorValidator(html)

    request.state.call_llm = False
    parsed = urlparse(req.url)
    url_path = parsed.path.rstrip("/")

    selector_type, selector_value, action = get_cached_locator(
        req.user_instruction, structure_html, url_path, project_id
    )
    if selector_type and selector_value:
        if verifier.verify(selector_type, selector_value):
            logger.info(
                f"Location verified: type: {selector_type}, value: {selector_value}"
            )
            action_type, action_value = (
                action.split(":") if action and action.find(":") >= 0 else ("", "")
            )
            return LocatorResponse(
                action_type=action_type,
                action_value=action_value,
                selector_type=selector_type,
                selector_value=selector_value,
            )
    selector = call_selector_llm(
        req.user_instruction,
        cleaned_html,
        MODEL_NAME,
        PROVIDER_NAME,
        req.conversation_history,
        metadata={
            "user_id": user.id,
            "project_id": project_id,
            "email": user.email,
        },
    )
    logger.info(f"Location found: {selector}")
    request.state.call_llm = True
    if selector is None:
        raise Exception("LLM invoke failed")
    action_type, action_value, selector_type, selector_value = (
        selector.action_type,
        selector.action_value,
        selector.selector_type,
        selector.selector_value,
    )
    request.state.input_tokens = len(req.user_instruction) + len(cleaned_html)
    request.state.output_tokens = len(selector_type) + len(selector_value)

    if verifier.verify(selector_type, selector_value):
        logger.info(
            f"Location verified: type: {selector_type}, value: {selector_value}"
        )
        save_locator(
            req.user_instruction,
            structure_html,
            selector_type,
            selector_value,
            action=":".join((action_type, action_value)),
            url=url_path,
            project_id=project_id,
            html=cleaned_html,
        )
        return LocatorResponse(
            action_type=action_type,
            action_value=action_value,
            selector_type=selector_type,
            selector_value=selector_value,
        )
    return LocatorResponse(
        action_type=action_type,
        action_value=action_value,
        selector_type=selector_type,
        selector_value=selector_value,
    )


@router.post("/locator-playground", response_model=LocatorResponse)
@limiter.limit("60/minute")
@playground_track_api_usage()
def locate_playground(
    req: LocatorRequest,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    html = req.html
    if not html:
        raise Exception("html is empty")
    try:
        cleaned_html = clean_html(html)
        structure_html = clean_html_keep_structure_only(cleaned_html)
        if cleaned_html is None:
            raise Exception(
                "make sure the html is valid and has meaningful information"
            )
        verifier = SelectorValidator(html)
    except Exception as err:
        logger.error(f"Failed to clean html: {err}")
        raise

    parsed = urlparse(req.url)
    url_path = parsed.path.rstrip("/")

    request.state.call_llm = False
    selector_type, selector_value, action = get_cached_locator(
        req.user_instruction, structure_html, url_path
    )
    if selector_type and selector_value:
        if verifier.verify(selector_type, selector_value):
            logger.info(
                f"Location verified: type: {selector_type}, value: {selector_value}"
            )
            action_type, action_value = (
                action.split(":") if action and action.find(":") >= 0 else ("", "")
            )
            return LocatorResponse(
                action_type=action,
                action_value=action_value,
                selector_type=selector_type,
                selector_value=selector_value,
            )
    selector = call_selector_llm(
        req.user_instruction,
        cleaned_html,
        MODEL_NAME,
        PROVIDER_NAME,
        req.conversation_history,
        metadata={
            "user_id": user.id,
            "email": user.email,
        },
    )
    logger.info(f"Location found: {selector}")
    request.state.call_llm = True
    if selector is None:
        raise Exception("LLM invoke failed")
    action_type, action_value, selector_type, selector_value = (
        selector.action_type,
        selector.action_value,
        selector.selector_type,
        selector.selector_value,
    )
    request.state.input_tokens = len(req.user_instruction) + len(cleaned_html)
    request.state.output_tokens = len(selector_type) + len(selector_value)

    if verifier.verify(selector_type, selector_value):
        logger.info(
            f"Location verified: type: {selector_type}, value: {selector_value}"
        )
        save_locator(
            req.user_instruction,
            structure_html,
            selector_type,
            selector_value,
            action=":".join((action_type, action_value)),
            url=url_path,
            html=cleaned_html,
        )
        return LocatorResponse(
            action_type=action_type,
            action_value=action_value,
            selector_type=selector_type,
            selector_value=selector_value,
        )
    return LocatorResponse(
        action_type=action_type,
        action_value=action_value,
        selector_type=selector_type,
        selector_value=selector_value,
    )
