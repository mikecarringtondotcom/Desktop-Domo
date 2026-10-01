"""Talking to Claude.

`ClaudeClient` is a thin wrapper over the official `anthropic` SDK.
`ClaudeWorker` runs a single request on a background thread so the chat
window doesn't freeze while we wait for a reply.
"""

import base64

import anthropic
from PySide6.QtCore import QThread, Signal

from desktop_domo import config, screenshot


def build_user_content(text, image_png=None):
    """Build a user message's ``content`` for the SDK.

    Returns a plain string when there's no image, or a list of content blocks
    ``[image, text]`` when a screenshot is attached. The image is downscaled
    (see ``config.VISION_MAX_EDGE``) to keep image input-token cost modest.
    The configured model supports vision, so this goes straight into the
    conversation.
    """
    if image_png is None:
        return text
    small = screenshot.downscale_png(image_png, config.VISION_MAX_EDGE)
    encoded = base64.standard_b64encode(small).decode("ascii")
    blocks = [{
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": encoded},
    }]
    if text:
        blocks.append({"type": "text", "text": text})
    return blocks


class ClaudeClient:
    """Wraps the Anthropic SDK. Raises RuntimeError if no API key is set."""

    # A server tool can hand the turn back mid-flight (stop_reason
    # "pause_turn") — a long web search, usually. We resume it a bounded
    # number of times rather than looping forever.
    MAX_RESUMES = 4

    def __init__(self):
        api_key = config.get_api_key()
        if not api_key:
            raise RuntimeError(
                f"No API key found. Set {config.API_KEY_ENV} in your "
                f"environment or in {config.ENV_FILE.name}."
            )
        # The SDK also reads ANTHROPIC_API_KEY on its own, but passing it
        # explicitly keeps behaviour obvious.
        self._client = anthropic.Anthropic(api_key=api_key)

    def reply(self, history):
        """Send the whole conversation and return Claude's reply text.

        `history` is a list of {"role": "user"|"assistant", "content": str}.
        """
        messages = list(history)
        for _ in range(self.MAX_RESUMES + 1):
            response = self._request(messages)
            if response.stop_reason != "pause_turn":
                return self._text_of(response)
            # Resume: hand the partial turn straight back, blocks untouched.
            messages = messages + [{"role": "assistant", "content": response.content}]
        return self._text_of(response)

    def _request(self, messages):
        """One call to the Messages API with our standing options."""
        kwargs = {
            "model": config.MODEL,
            "max_tokens": config.MAX_TOKENS,
            "system": config.SYSTEM_PROMPT,
            "messages": messages,
            "output_config": {"effort": config.EFFORT},
        }
        if config.ENABLE_WEB_SEARCH:
            kwargs["tools"] = [{
                "type": config.WEB_SEARCH_TOOL,
                "name": "web_search",
                "max_uses": config.WEB_SEARCH_MAX_USES,
            }]
        if not config.ENABLE_REFUSAL_FALLBACK:
            return self._client.messages.create(**kwargs)
        # Refusal fallback lives on the beta endpoint: on a policy decline the
        # API reruns the request on a fallback model inside the same call.
        return self._client.beta.messages.create(
            betas=[config.FALLBACK_BETA], fallbacks="default", **kwargs
        )

    @staticmethod
    def _text_of(response):
        """Pull the visible reply out of a response's content blocks."""
        # The response content is a list of blocks; pull out the text ones.
        # Thinking and server-tool blocks are deliberately skipped.
        parts = [block.text for block in response.content if block.type == "text"]
        text = "".join(parts).strip()
        if text:
            return text
        # An empty reply is nearly always a refusal or a blown token cap;
        # say which instead of leaving a blank line in the transcript.
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            reason = getattr(details, "explanation", None) or "no reason given"
            return f"[Domo declined to answer this one: {reason}]"
        if response.stop_reason == "max_tokens":
            return (
                "[Ran out of room before writing an answer. Raise MAX_TOKENS "
                "or lower EFFORT in desktop_domo/config.py.]"
            )
        return "[Empty reply from Claude.]"


class ClaudeWorker(QThread):
    """Runs one `ClaudeClient.reply()` call off the UI thread."""

    succeeded = Signal(str)   # emits the reply text
    failed = Signal(str)      # emits a human-readable error message

    def __init__(self, client, history, parent=None):
        super().__init__(parent)
        self._client = client
        # Copy so later edits to the window's history don't affect this run,
        # keeping only the fields the API accepts (the chat also stores `time`).
        self._history = [
            {"role": m["role"], "content": m["content"]} for m in history
        ]

    def run(self):
        try:
            text = self._client.reply(self._history)
            self.succeeded.emit(text)
        except Exception as exc:  # surface any failure to the UI, don't crash
            self.failed.emit(str(exc))
