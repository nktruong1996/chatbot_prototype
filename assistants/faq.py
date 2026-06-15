from config import client, CHAT_MODEL, SUPPORT_CONTACT
from models import FAQRequest, FAQResponse
# from retrieval import retrieve
from retrieval_sql import retrieve
from prompts import (
    INTENT_PROMPT,
    FAQ_SYSTEM_PROMPT,
    FAQ_NO_CONTEXT_NOTE,
    FAQ_TIER1_RESPONSE,
    FAQ_TIER2_RESPONSE,
)


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

# def detect_intent(message: str) -> str:
#     """Returns 'PORTAL' or 'OFF_TOPIC'. Defaults to PORTAL if unexpected output."""
#     prompt = INTENT_PROMPT.format(message=message)
#     response = client.chat.completions.create(
#         model=CHAT_MODEL,
#         messages=[{"role": "user", "content": prompt}],
#         max_tokens=10,
#         temperature=0,
#     )
#     raw = response.choices[0].message.content.strip().upper()

#     if raw in ("PORTAL", "OFF_TOPIC"):
#         return raw

#     print(f"[intent] Unexpected output '{raw}', defaulting to PORTAL")
#     return "PORTAL"

def detect_intent(message: str, history: list = []) -> str:
    """Returns 'PORTAL' or 'OFF_TOPIC'. Defaults to OFF_TOPIC if unexpected output."""
    # prompt = INTENT_PROMPT.format(message=message)
    context = ""
    if history:
        last_turns = history[-4:]
        context = "Recent conversation:\n" + "\n".join(f"{t.role}: {t.content}" for t in last_turns)
    prompt = INTENT_PROMPT.format(message=message, context=context)

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip().upper()

    if raw in ("PORTAL", "OFF_TOPIC"):
        return raw

    print(f"[intent] Unexpected output '{raw}', defaulting to OFF_TOPIC")
    return "OFF_TOPIC"

# ---------------------------------------------------------------------------
# Confidence check
# ---------------------------------------------------------------------------

UNCERTAINTY_PHRASES = (
    "i don't know",
    "i'm not sure",
    "i cannot find",
    "i do not have",
    "no information",
    "unable to answer",
    "cannot answer",
    "not in my knowledge",
)

def seems_uncertain(answer: str) -> bool:
    lower = answer.lower()
    return any(phrase in lower for phrase in UNCERTAINTY_PHRASES)


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

def handle_faq(req: FAQRequest) -> FAQResponse:
    # 1. Intent detection
    # intent = detect_intent(req.message)
    intent = detect_intent(req.message, req.history)

    if intent == "OFF_TOPIC":
        return FAQResponse(
            answer=FAQ_TIER1_RESPONSE,
            fallback=True,
            fallback_type="tier1",
            support_contact=None,
        )

    # 2. Retrieve relevant chunks
    chunks = retrieve(req.message)
    context = "\n\n---\n\n".join(chunks) if chunks else FAQ_NO_CONTEXT_NOTE

    # 3. Build messages
    messages = [{"role": "system", "content": FAQ_SYSTEM_PROMPT.format(context=context)}]

    for turn in req.history:
        messages.append({"role": turn.role, "content": turn.content})

    messages.append({"role": "user", "content": req.message})

    # 4. Single LLM call
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        max_tokens=500,
        temperature=0.3,
    )
    answer = response.choices[0].message.content.strip()

    # 5. Tier 2 fallback
    if seems_uncertain(answer) or not chunks:
        return FAQResponse(
            answer=FAQ_TIER2_RESPONSE.format(support_contact=SUPPORT_CONTACT),
            fallback=True,
            fallback_type="tier2",
            support_contact=SUPPORT_CONTACT,
        )

    return FAQResponse(
        answer=answer,
        fallback=False,
        fallback_type=None,
        support_contact=None,
    )