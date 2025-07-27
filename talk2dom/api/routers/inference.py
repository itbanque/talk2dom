from fastapi import APIRouter, HTTPException, Depends, Request

from talk2dom.core import call_selector_llm, retry
from talk2dom.db.cache import get_cached_locator, save_locator
from talk2dom.db.session import Session, get_db
from talk2dom.api.schemas import LocatorRequest, LocatorResponse
from talk2dom.api.utils.validator import SelectorValidator
from talk2dom.api.utils.html_cleaner import clean_html, clean_html_keep_structure_only
from loguru import logger
from talk2dom.db.models import User
from talk2dom.api.deps import (
    get_api_key_user,
    track_api_usage,
    get_api_key_id,
    get_current_project_id,
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

    try:
        structure_html = clean_html_keep_structure_only(req.html)
        cleaned_html = clean_html(req.html)
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
            "gpt-4o",
            "openai",
            req.conversation_history,
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
                selector_type=selector_type, selector_value=selector_value
            )
        raise HTTPException(status_code=500, detail="Location not found")
    except Exception as e:
        logger.error(f"Location failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
