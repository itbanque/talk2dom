from fastapi import APIRouter, HTTPException, Depends, Request
from talk2dom.core import call_selector_llm, retry
from talk2dom.db.cache import get_cached_locator, save_locator
from talk2dom.db.session import Session, get_db
from talk2dom.api.schemas import LocatorRequest, LocatorResponse
from talk2dom.api.utils.validator import SelectorValidator
from talk2dom.api.utils.html_cleaner import clean_html
from loguru import logger
from talk2dom.db.models import User
from talk2dom.api.deps import get_api_key_user, track_api_usage, get_api_key_id

router = APIRouter()  #


@router.post("/locator", response_model=LocatorResponse)
@retry()
@track_api_usage()
def locate(
    req: LocatorRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_api_key_user),
    api_key_id: str = Depends(get_api_key_id),
):
    try:
        cleaned_html = clean_html(req.html)
        verifier = SelectorValidator(cleaned_html)
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

    try:
        request.state.call_llm = False
        selector_type, selector_value = get_cached_locator(
            req.user_instruction, cleaned_html, req.url
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
            req.model,
            req.model_provider,
            req.conversation_history,
        )
        request.state.call_llm = True
        request.state.input_tokens = len(req.user_instruction) + len(cleaned_html)
        request.state.output_tokens = len(selector_type) + len(selector_value)
        selector_type, selector_value = selector.selector_type, selector.selector_value

        if verifier.verify(selector_type, selector_value):
            logger.info(
                f"Location verified: type: {selector_type}, value: {selector_value}"
            )
            save_locator(
                req.user_instruction,
                cleaned_html,
                selector_type,
                selector_value,
                req.url,
            )
            return LocatorResponse(
                selector_type=selector_type, selector_value=selector_value
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
