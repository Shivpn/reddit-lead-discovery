"""
llm_client.py — Unified LLM interface for Reddit Lead Discovery
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION  — change LLM_PROVIDER (and matching key) in .env only
# ─────────────────────────────────────────────────────────────────────

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'groq').lower()

# Default models per provider (override with LLM_MODEL in .env)
_DEFAULT_MODELS = {
    'groq':      'llama-3.3-70b-versatile',
    'openai':    'gpt-4o-mini',
    'anthropic': 'claude-haiku-4-5-20251001',
}

LLM_MODEL = os.getenv('LLM_MODEL', _DEFAULT_MODELS.get(LLM_PROVIDER, ''))

print(f"[LLM] Provider: {LLM_PROVIDER.upper()} | Model: {LLM_MODEL}")


# ─────────────────────────────────────────────────────────────────────
# CLIENT INITIALISATION
# ─────────────────────────────────────────────────────────────────────

def _init_client():
    if LLM_PROVIDER == 'groq':
        from groq import Groq
        return Groq(api_key=os.getenv('GROQ_API_KEY'))

    elif LLM_PROVIDER == 'openai':
        from openai import OpenAI
        return OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    elif LLM_PROVIDER == 'anthropic':
        import anthropic
        return anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{LLM_PROVIDER}'. "
            "Choose: groq | openai | anthropic"
        )


_client = _init_client()


# ─────────────────────────────────────────────────────────────────────
# UNIFIED CALL FUNCTION
# Drop-in replacement for the old call_groq_ai() in app_with_db.py
# ─────────────────────────────────────────────────────────────────────

def call_llm(system_prompt: str,
             user_message: str,
             temperature: float = 0.3,
             max_tokens: int = 500) -> tuple[str | None, int, int]:
    """
    Call the configured LLM provider.

    Returns
    -------
    (text, prompt_tokens, completion_tokens)
        text is None on failure.
    """
    try:
        if LLM_PROVIDER in ('groq', 'openai'):
            # Both use the OpenAI-compatible SDK interface
            response = _client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content.strip()
            usage = response.usage
            pt = usage.prompt_tokens     if usage else 0
            ct = usage.completion_tokens if usage else 0
            return text, pt, ct

        elif LLM_PROVIDER == 'anthropic':
            response = _client.messages.create(
                model=LLM_MODEL,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                temperature=temperature,
            )
            text = response.content[0].text.strip()
            pt = response.usage.input_tokens  if response.usage else 0
            ct = response.usage.output_tokens if response.usage else 0
            return text, pt, ct

    except Exception as e:
        print(f"[LLM/{LLM_PROVIDER}] Error: {e}")
        return None, 0, 0
