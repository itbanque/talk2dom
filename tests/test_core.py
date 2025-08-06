from unittest.mock import MagicMock, patch


from talk2dom.core import (
    call_selector_llm,
)


@patch("talk2dom.core.init_chat_model")
@patch("talk2dom.core.load_prompt", return_value="prompt")
def test_call_selector_llm(mock_prompt, mock_model):
    fake_chain = MagicMock()
    fake_chain.invoke.return_value = [
        MagicMock(selector_type="id", selector_value="main")
    ]
    mock_model.return_value.bind_tools.return_value.__or__.return_value = fake_chain

    result = call_selector_llm("click", "<div></div>", "model", "provider")
    assert result.selector_type == "id"
    assert result.selector_value == "main"
