# llm_integration.py
import os
import threading
import time

# Try GPT4All local model first
try:
    from gpt4all import GPT4All
    GPT4ALL_AVAILABLE = True
except Exception:
    GPT4ALL_AVAILABLE = False

# OpenAI fallback
try:
    import openai
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False

# configure model path (if using local)
LOCAL_MODEL_PATH = os.environ.get("GPT4ALL_MODEL_PATH", "models/gpt4all-model.bin")

gpt4all_bot = None
if GPT4ALL_AVAILABLE and os.path.exists(LOCAL_MODEL_PATH):
    gpt4all_bot = GPT4All(model=LOCAL_MODEL_PATH)

def ask_local_gpt4all(prompt, max_tokens=256):
    if not gpt4all_bot:
        raise RuntimeError("Local GPT4All model not available.")
    # simple synchronous generate
    resp = gpt4all_bot.generate(prompt, max_length=max_tokens)
    return resp

def ask_openai(prompt, model="gpt-3.5-turbo", max_tokens=256):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    openai.api_key = key
    completion = openai.ChatCompletion.create(
        model=model,
        messages=[{"role":"user","content":prompt}],
        max_tokens=max_tokens,
        temperature=0.2
    )
    return completion.choices[0].message.content

def ask_llm(prompt):
    # prefer local
    if GPT4ALL_AVAILABLE and os.path.exists(LOCAL_MODEL_PATH):
        try:
            return ask_local_gpt4all(prompt)
        except Exception as e:
            # fallback to OpenAI if configured
            print("gpt4all failed:", e)
    if OPENAI_AVAILABLE and os.environ.get("OPENAI_API_KEY"):
        return ask_openai(prompt)
    raise RuntimeError("No LLM available. Install gpt4all and download model, or set OPENAI_API_KEY")
