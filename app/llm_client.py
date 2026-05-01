"""LLM Client: Talk to local llama.cpp server.

Handles streaming responses, context injection, and model management.
"""
from __future__ import annotations

import json
import re
from typing import Generator, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

from app.client import RuntimeConfig


class LLMClient:
    """Interface to local llama.cpp HTTP server."""

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.base_url = config.base_url
        self.model = config.model

    def _is_alive(self) -> bool:
        """Check if server is responding."""
        try:
            request = Request(f"{self.base_url}/v1/models", method="GET")
            with urlopen(request, timeout=3):
                return True
        except (URLError, Exception):
            return False

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop_tokens: Optional[tuple] = None,
    ) -> Generator[str, None, None]:
        """Stream tokens from the model.
        
        Args:
            prompt: User message
            system: System prompt override
            max_tokens: Max output tokens (default: config.num_predict)
            temperature: Temperature override
            top_p: Top-p override
            stop_tokens: Stop token override
        
        Yields:
            Token strings
        """
        if not self._is_alive():
            raise RuntimeError(
                f"LLM server not responding at {self.base_url}. "
                "Make sure llama.cpp server is running."
            )

        # Build message list
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Build request
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.num_predict,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "top_p": top_p if top_p is not None else self.config.top_p,
            "stream": True,
        }

        if stop_tokens or self.config.stop_tokens:
            payload["stop"] = list(stop_tokens or self.config.stop_tokens)

        # Send request
        try:
            headers = {"Content-Type": "application/json"}
            data = json.dumps(payload).encode("utf-8")
            request = Request(
                f"{self.base_url}/v1/chat/completions",
                data=data,
                headers=headers,
                method="POST",
            )

            with urlopen(request, timeout=120) as response:
                buffer = ""
                for chunk in response:
                    buffer += chunk.decode("utf-8")
                    # Parse SSE (Server-Sent Events)
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if not line or line == "[DONE]":
                            continue
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if "choices" in data:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                pass

        except URLError as e:
            raise RuntimeError(f"LLM request failed: {e}")

    def generate_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate full text (non-streaming).
        
        Args:
            prompt: User message
            system: System prompt override
            max_tokens: Max output tokens
        
        Returns:
            Full generated text
        """
        tokens = []
        for token in self.generate(prompt, system, max_tokens):
            tokens.append(token)
        return "".join(tokens)
