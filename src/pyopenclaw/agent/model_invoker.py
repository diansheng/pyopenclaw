import logging
import asyncio
import aiohttp
import json
import os
from typing import List, Dict, Any, AsyncIterator, Optional
from pyopenclaw.config import LLMConfig, LLMProviderConfig

logger = logging.getLogger(__name__)

class NoProvidersAvailable(Exception):
    pass

class ModelResponse:
    def __init__(self, text: str, tool_calls: Optional[List[Dict[str, Any]]] = None, finish_reason: str = "stop", usage: Dict[str, int] = None):
        self.text = text
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason
        self.usage = usage or {}

class ModelInvoker:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._clients = {}

    async def invoke(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> ModelResponse:
        provider = self._select_provider()
        if not provider:
            raise NoProvidersAvailable("No healthy LLM providers available.")

        try:
            if provider.name == "openai":
                return await self._invoke_openai(provider, messages, tools)
            elif provider.name == "anthropic":
                return await self._invoke_anthropic(provider, messages, tools)
            elif provider.name == "gemini":
                return await self._invoke_gemini(provider, messages, tools)
            elif provider.name == "minimax":
                return await self._invoke_minimax(provider, messages, tools)
            else:
                raise ValueError(f"Unsupported provider: {provider.name}")
        except Exception as e:
            logger.error(f"Invocation failed for {provider.name}: {e}")
            # Here we should handle rate limits and retry with next provider
            # For MVP, just raise
            raise

    async def invoke_streaming(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> AsyncIterator[str]:
        # Simple streaming stub
        response = await self.invoke(messages, tools)
        yield response.text

    def _select_provider(self) -> Optional[LLMProviderConfig]:
        # Simple priority selection
        sorted_providers = sorted(self.config.providers, key=lambda p: p.priority)
        if not sorted_providers:
             return None
        return sorted_providers[0]

    async def _invoke_openai(self, provider: LLMProviderConfig, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> ModelResponse:
        from openai import AsyncOpenAI
        import os
        
        client = self._get_openai_client(provider)
        
        # Convert tools to OpenAI format
        openai_tools = None
        if tools:
            openai_tools = [{"type": "function", "function": t} for t in tools]
            
        response = await client.chat.completions.create(
            model=provider.model,
            messages=messages,
            tools=openai_tools
        )
        
        choice = response.choices[0]
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
                
        return ModelResponse(
            text=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            usage=dict(response.usage) if response.usage else {}
        )

    async def _invoke_anthropic(self, provider: LLMProviderConfig, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> ModelResponse:
        # Stub for Anthropic
        raise NotImplementedError("Anthropic provider not yet implemented")

    async def _invoke_gemini(self, provider: LLMProviderConfig, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> ModelResponse:
        api_key = os.environ.get(provider.api_key_env)
        if not api_key:
            raise ValueError(f"API key env var {provider.api_key_env} not set")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{provider.model}:generateContent?key={api_key}"
        
        # Convert messages to Gemini format
        # User: role="user", parts=[{"text": ...}]
        # Model: role="model", parts=[{"text": ...}]
        gemini_contents = []
        system_instruction = None
        
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
                continue
                
            if role == "assistant":
                role = "model"
            
            # Handle tool calls/results if needed (simplified for MVP)
            # Gemini tool use structure is different. For now, text only.
            
            gemini_contents.append({
                "role": role,
                "parts": [{"text": content}]
            })

        payload = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": 0.7
            }
        }
        
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Gemini API error {resp.status}: {error_text}")
                
                data = await resp.json()
                
        # Parse response
        # data["candidates"][0]["content"]["parts"][0]["text"]
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return ModelResponse(text=text)
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse Gemini response: {data}")
            raise Exception(f"Invalid Gemini response format: {e}")

    async def _invoke_minimax(self, provider: LLMProviderConfig, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> ModelResponse:
        api_key = os.environ.get(provider.api_key_env)
        group_id = os.environ.get("MINIMAX_GROUP_ID", "")
        
        if not api_key:
            raise ValueError(f"API key env var {provider.api_key_env} not set")

        # Minimax API URL (standard chat completion)
        url = f"https://api.minimax.chat/v1/text/chatcompletion_pro?GroupId={group_id}"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Convert messages
        minimax_messages = []
        bot_setting = []
        
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")
            
            if role == "system":
                # Minimax often treats system prompt as "bot_setting" or just a message
                # "prompt" field or "bot_setting"
                bot_setting.append({
                    "bot_name": "Assistant",
                    "content": content
                })
                continue
                
            sender_type = "USER" if role == "user" else "BOT"
            sender_name = "User" if role == "user" else "Assistant"
            
            minimax_messages.append({
                "sender_type": sender_type,
                "sender_name": sender_name,
                "text": content
            })

        payload = {
            "model": provider.model,
            "messages": minimax_messages,
            "bot_setting": bot_setting,
            "reply_constraints": {"sender_type": "BOT", "sender_name": "Assistant"},
            "temperature": 0.7,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Minimax API error {resp.status}: {error_text}")
                
                data = await resp.json()
                
        # Parse response
        # data["reply"]
        try:
            text = data["reply"]
            return ModelResponse(text=text)
        except KeyError:
            logger.error(f"Failed to parse Minimax response: {data}")
            raise Exception("Invalid Minimax response format")

    def _get_openai_client(self, provider: LLMProviderConfig):
        from openai import AsyncOpenAI
        import os
        if provider.name not in self._clients:
            api_key = os.environ.get(provider.api_key_env)
            if not api_key:
                raise ValueError(f"API key env var {provider.api_key_env} not set")
            self._clients[provider.name] = AsyncOpenAI(api_key=api_key)
        return self._clients[provider.name]
