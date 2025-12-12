# ai_module.py
# Offline LLM Assistant Module for Cargo Platform (Using Ollama)

import subprocess
import json
import re


# ---------------------------------------------------------
# RUN OFFLINE MODEL (LLaMA / Mistral / Phi3 etc.)
# ---------------------------------------------------------
def ask_ai(prompt, model="llama3"):
    """
    Sends a prompt to the local Ollama LLM model.
    Example model names: llama3, mistral, phi3, gemma.
    """

    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        answer = result.stdout.decode("utf-8")
        return clean_output(answer)

    except Exception as e:
        return f"AI engine error: {e}"


# ---------------------------------------------------------
# CLEAN LLM OUTPUT (REMOVE TOKENS, JSON MARKERS, ETC.)
# ---------------------------------------------------------
def clean_output(text):
    # Remove code fences
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"```", "", text)

    # Remove unwanted artifacts
    text = text.replace("<|assistant|>", "").replace("<|end|>", "")
    return text.strip()


# ---------------------------------------------------------
# SMART ROUTE ANALYZER
# ---------------------------------------------------------
def analyze_route(flight1, flight2):
    """
    Takes 2 legs and returns an AI explanation.
    """

    prompt = f"""
You are an aviation cargo expert.

Analyze this interline cargo route and explain:

- Total available capacity
- Risk factors (delay, mismatching cargo type)
- Best cargo suitable
- Cost efficiency
- Operational issues

Leg 1:
  Airline: {flight1['airline']}
  Flight: {flight1['flight_no']}
  Route: {flight1['origin']} → {flight1['destination']}
  Date: {flight1['date']}
  Capacity: {flight1['capacity']} kg
  Cargo Type: {flight1.get('cargo_type', 'General')}

Leg 2:
  Airline: {flight2['airline']}
  Flight: {flight2['flight_no']}
  Route: {flight2['origin']} → {flight2['destination']}
  Date: {flight2['date']}
  Capacity: {flight2['capacity']} kg
  Cargo Type: {flight2.get('cargo_type', 'General')}

Give the explanation in 5 bullet points.
"""
    return ask_ai(prompt)



# ---------------------------------------------------------
# CARGO RISK ANALYZER
# ---------------------------------------------------------
def cargo_risk(cargo_type):
    """
    AI predicts risks for a given type of cargo.
    """

    prompt = f"""
You are a cargo operations expert.

Explain the operational risks, temperature needs,
paperwork, handling challenges, and routing concerns for:

Cargo Type: {cargo_type}

Give the answer in bullet points.
"""

    return ask_ai(prompt)



# ---------------------------------------------------------
# CAPACITY PREDICTION (AI-BASED)
# ---------------------------------------------------------
def predict_capacity(airline, origin, destination):
    """
    AI predicts expected cargo capacity based on patterns.
    No real ML model needed — LLM reasoning.
    """

    prompt = f"""
Predict expected cargo capacity for an upcoming flight.

Airline: {airline}
Route: {origin} → {destination}

Consider:
- Seasonal patterns
- Typical cargo loads on this route
- Aircraft type (assume typical for airline)
- Historical averages (LLM reasoning)

Give capacity range in kg + short explanation.
"""

    return ask_ai(prompt)



# ---------------------------------------------------------
# CHATBOT FOR USER PORTAL
# ---------------------------------------------------------
def chat_with_ai(message):
    """
    General assistant for your platform.
    """

    prompt = f"""
You are CargoAI — an intelligent cargo assistant.

User asked:
{message}

Give a helpful and concise reply.
"""

    return ask_ai(prompt)
