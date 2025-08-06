from fastapi import APIRouter, HTTPException, Depends, Request

from talk2dom.core import call_selector_llm, retry, get_page_content
from talk2dom.db.cache import get_cached_locator, save_locator
from talk2dom.db.session import Session, get_db
from talk2dom.api.schemas import LocatorRequest, LocatorResponse
from talk2dom.api.utils.validator import SelectorValidator
from talk2dom.api.utils.html_cleaner import (
    clean_html,
    clean_html_keep_structure_only,
    convert_relative_paths_to_absolute,
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
    if not req.html:
        html = get_page_content(req.url, req.view)
    else:
        html = req.html
    try:
        structure_html = clean_html_keep_structure_only(html)
        cleaned_html = clean_html(html)
        verifier = SelectorValidator(cleaned_html)
    except Exception as err:
        logger.error(f"Failed to clean html: {err}")
        raise HTTPException(status_code=500, detail="Invalid HTML")

    try:
        request.state.call_llm = False
        selector_type, selector_value = get_cached_locator(
            req.user_instruction, structure_html, req.url, project_id
        )
        if selector_type and selector_value:
            if verifier.verify(selector_type, selector_value):
                logger.info(
                    f"Location verified: type: {selector_type}, value: {selector_value}"
                )
                return LocatorResponse(
                    selector_type=selector_type,
                    selector_value=selector_value,
                )
        selector = call_selector_llm(
            req.user_instruction,
            cleaned_html,
            "gemini-2.5-pro",
            "google_genai",
            req.conversation_history,
            metadata={
                "user_id": user.id,
                "project_id": project_id,
                "email": user.email,
            },
        )
        logger.info(f"Location found: {selector}")
        request.state.call_llm = True
        selector_type, selector_value = selector.selector_type, selector.selector_value
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
                req.url,
                project_id=project_id,
                html=cleaned_html,
            )
            return LocatorResponse(
                selector_type=selector_type,
                selector_value=selector_value,
                page_html=html if not req.html else None,
            )
        raise HTTPException(status_code=500, detail="Location not found")
    except Exception as e:
        logger.error(f"Location failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/locator-playground", response_model=LocatorResponse)
@limiter.limit("60/minute")
@playground_track_api_usage()
def locate_playground(
    req: LocatorRequest,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    html = get_page_content(req.url, req.view)
    html = convert_relative_paths_to_absolute(html, req.url)
    try:
        structure_html = clean_html_keep_structure_only(html)
        cleaned_html = clean_html(html)
        verifier = SelectorValidator(cleaned_html)
    except Exception as err:
        logger.error(f"Failed to clean html: {err}")
        raise HTTPException(status_code=500, detail="Invalid HTML")

    try:
        request.state.call_llm = False
        selector_type, selector_value = get_cached_locator(
            req.user_instruction, structure_html, req.url
        )
        if selector_type and selector_value:
            if verifier.verify(selector_type, selector_value):
                logger.info(
                    f"Location verified: type: {selector_type}, value: {selector_value}"
                )
                return LocatorResponse(
                    selector_type=selector_type,
                    selector_value=selector_value,
                    page_html=html,
                )
        selector = call_selector_llm(
            req.user_instruction,
            cleaned_html,
            "gemini-2.5-pro",
            "google_genai",
            req.conversation_history,
            metadata={
                "user_id": user.id,
                "email": user.email,
            },
        )
        logger.info(f"Location found: {selector}")
        request.state.call_llm = True
        selector_type, selector_value = selector.selector_type, selector.selector_value
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
                req.url,
                html=cleaned_html,
            )
            return LocatorResponse(
                selector_type=selector_type,
                selector_value=selector_value,
                page_html=html,
            )
        raise HTTPException(status_code=500, detail="Location not found")
    except Exception as e:
        logger.error(f"Location failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
