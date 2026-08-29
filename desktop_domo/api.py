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
    Opus 4.8 supports vision, so this goes straight into the conversation.
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
        response = self._client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            system=config.SYSTEM_PROMPT,
            messages=history,
        )
        # The response content is a list of blocks; pull out the text ones.
        parts = [block.text for block in response.content if block.type == "text"]
        return "".join(parts).strip()


class ClaudeWorker(QThread):
    """Runs one `ClaudeClient.reply()` call off the UI thread."""

    succeeded = Signal(str)   # emits the reply text
    failed = Signal(str)      # emits a human-readable error message

    def __init__(self, client, history, parent=None):
        super().__init__(parent)
        self._client = client
        # Copy so later edits to the window's history don't affect this run.
        self._history = list(history)

    def run(self):
        try:
            text = self._client.reply(self._history)
            self.succeeded.emit(text)
        except Exception as exc:  # surface any failure to the UI, don't crash
            self.failed.emit(str(exc))
