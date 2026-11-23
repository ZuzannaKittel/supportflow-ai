
import json
import os
import re
from uuid import uuid4

from dotenv import load_dotenv

from app import tools as business_tools


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

MAX_TOOL_ITERATIONS = 5

# Conversations are stored in memory for this MVP.
CONVERSATIONS = {}


# --------------------------------------------------
# TOOL REGISTRY
# --------------------------------------------------

TOOL_FUNCTIONS = {
    "get_order": business_tools.get_order,
    "track_delivery": business_tools.track_delivery,
    "check_refund_eligibility": business_tools.check_refund_eligibility,
    "process_refund": business_tools.process_refund,
    "escalate_to_human": business_tools.escalate_to_human,
}


# --------------------------------------------------
# OPENAI FUNCTION DEFINITIONS
# --------------------------------------------------

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Retrieve order details, items, customer and order status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The customer's order ID."
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "track_delivery",
            "description": "Retrieve shipping status and estimated delivery information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"}
                },
                "required": ["order_id"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_refund_eligibility",
            "description": "Check whether an order qualifies for a refund request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"}
                },
                "required": ["order_id"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_refund",
            "description": (
                "Create a simulated refund request. "
                "Only use after an explicit customer request to submit a refund "
                "and when the customer has provided a reason."
                "This does not refund an actual payment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "reason": {
                        "type": "string",
                        "description": "The customer's explicitly provided refund reason."
                    }
                },
                "required": ["order_id", "reason"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Create a support ticket for a human support representative.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "conversation_summary": {"type": "string"}
                },
                "required": ["reason", "conversation_summary"],
                "additionalProperties": False
            }
        }
    }
]


# --------------------------------------------------
# AGENT CONFIGURATION
# --------------------------------------------------

SYSTEM_PROMPT = """
You are SupportFlow AI, a customer support assistant for a fictional
e-commerce company.

Your job is to help customers with orders, delivery and refunds.

AVAILABLE TOOLS:
- get_order
- track_delivery
- check_refund_eligibility
- process_refund
- escalate_to_human

RULES:

1. Always use actual tool results for order and delivery information.
2. Never invent order details, tracking information or delivery dates.
3. Ask for the order ID if it is missing.
4. Check refund eligibility before processing a refund.
5. Only create a refund request when the customer explicitly asks
   to submit a refund and has provided a reason.
6. Never claim that an actual payment has been refunded.
   Refund requests are simulated.
7. Never invent a customer's refund reason.
8. Escalate requests involving fraud, payment disputes, legal issues,
   account security or situations requiring human assistance.
9. If a tool returns an error, explain it honestly.
10. Be concise, professional and empathetic.

You are a single AI agent using external business tools.
Do not claim that you have performed actions that the tools did not execute.
"""


def get_agent_mode():
    return "openai" if OPENAI_API_KEY else "deterministic"


# --------------------------------------------------
# SHARED HELPERS
# --------------------------------------------------

def _extract_order_id(text):
    match = re.search(r"#?(\d{4,})", text)
    return match.group(1) if match else None


def _get_previous_order_id(messages):
    for message in reversed(messages):
        if message.get("role") == "user":
            order_id = _extract_order_id(message.get("content", ""))
            if order_id:
                return order_id

    return None


def _get_user_history(messages):
    return " ".join(
        message.get("content", "")
        for message in messages
        if message.get("role") == "user"
    )


def _has_refund_intent(text):
    return bool(re.search(
        r"\b(refund|money back)\b",
        text,
        re.IGNORECASE
    ))


def _has_explicit_refund_request(text):
    return bool(re.search(
        r"\b("
        r"i want|i need|i'd like|i would like|"
        r"please submit|please process|please request|"
        r"submit|process|initiate|request"
        r")\b",
        text,
        re.IGNORECASE
    )) and _has_refund_intent(text)


def _has_refund_reason(text):
    reason_keywords = [
        "damaged",
        "broken",
        "defective",
        "faulty",
        "wrong item",
        "incorrect item",
        "missing item",
        "not working",
        "arrived late",
        "changed my mind",
        "no longer needed",
        "not as described",
        "poor quality",
    ]

    text = text.lower()

    return any(keyword in text for keyword in reason_keywords)


def _extract_refund_reason(text):
    match = re.search(
        r"\b(?:because|since|reason is|as)\s+(.+)",
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip(" .!?")

    reason_keywords = [
        "damaged", "broken", "defective", "faulty",
        "wrong item", "incorrect item", "missing item",
        "not working", "arrived late", "changed my mind",
        "no longer needed", "not as described", "poor quality"
    ]

    for keyword in reason_keywords:
        if keyword in text.lower():
            return keyword

    return None


def _execute_tool(name, arguments, user_history):
    """Validate and execute an allowed business tool."""

    if name not in TOOL_FUNCTIONS:
        return {
            "success": False,
            "error": f"Unknown tool: {name}"
        }

    if not isinstance(arguments, dict):
        return {
            "success": False,
            "error": "Tool arguments must be an object."
        }

    
    if name == "process_refund":

        # Require an explicit customer refund request.
        if not _has_explicit_refund_request(user_history):
            return {
                "success": False,
                "error": "An explicit customer refund request is required."
            }

        # Extract and validate the reason.
        reason = arguments.get("reason", "") if isinstance(arguments, dict) else ""

        if not isinstance(reason, str) or not reason.strip():
            return {
                "success": False,
                "error": "A refund reason is required."
            }

        # The customer must have provided a recognizable reason.
        if not _has_refund_reason(user_history):
            return {
                "success": False,
                "error": "The customer must provide a refund reason."
            }

        if not _has_refund_reason(reason):
            return {
                "success": False,
                "error": "The refund reason must reflect information provided by the customer."
            }


    try:
        result = TOOL_FUNCTIONS[name](**arguments)

        if not isinstance(result, dict):
            return {
                "success": False,
                "error": "Unexpected tool result."
            }

        return result

    except TypeError:
        return {
            "success": False,
            "error": "Invalid tool arguments."
        }

    except Exception:
        return {
            "success": False,
            "error": "An internal business tool error occurred."
        }


def _build_tool_trace(name, arguments, result):
    return {
        "tool": name,
        "arguments": arguments,
        "result": result
    }


def _build_response(
    conversation_id,
    response,
    tool_calls,
    agent_mode,
    escalated=False,
    ticket_id=None
):
    return {
        "conversation_id": conversation_id,
        "response": response,
        "tool_calls": tool_calls,
        "escalated": escalated,
        "ticket_id": ticket_id,
        "agent_mode": agent_mode
    }


# --------------------------------------------------
# DETERMINISTIC FALLBACK AGENT
# --------------------------------------------------

def _run_deterministic_agent(
    conversation_id,
    message,
    history
):
    text = message.lower()
    user_history = _get_user_history(
        history + [{"role": "user", "content": message}]
    )

    tool_calls = []

    order_id = (
        _extract_order_id(message)
        or _get_previous_order_id(history)
    )

    # 1. Human escalation
    escalation_keywords = [
        "human",
        "representative",
        "speak to someone",
        "real person",
        "fraud",
        "chargeback",
        "legal issue",
        "account compromised",
        "account hacked",
    ]

    if any(keyword in text for keyword in escalation_keywords):
        reason = "Customer requested or requires human assistance."

        result = _execute_tool(
            "escalate_to_human",
            {
                "reason": reason,
                "conversation_summary": (
                    f"Customer conversation: {user_history}"
                )
            },
            user_history
        )

        tool_calls.append(
            _build_tool_trace(
                "escalate_to_human",
                {"reason": reason},
                result
            )
        )

        ticket_id = (
            result.get("ticket", {}).get("ticket_id")
            if result.get("success")
            else None
        )

        response = (
            f"I've created a support ticket ({ticket_id}). "
            "A human support representative will need to assist you."
            if ticket_id
            else "I couldn't create the support ticket. Please try again."
        )

        return _build_response(
            conversation_id,
            response,
            tool_calls,
            "deterministic",
            escalated=bool(ticket_id),
            ticket_id=ticket_id
        )

    # 2. Missing order ID
    if not order_id and any(
        keyword in text
        for keyword in [
            "order", "delivery", "package",
            "refund", "shipment", "tracking"
        ]
    ):
        return _build_response(
            conversation_id,
            "I'd be happy to help. Could you provide your order ID?",
            [],
            "deterministic"
        )

    # 3. Refund request
    if _has_refund_intent(text):
        if not _has_explicit_refund_request(user_history):
            result = _execute_tool(
                "check_refund_eligibility",
                {"order_id": order_id},
                user_history
            )

            tool_calls.append(
                _build_tool_trace(
                    "check_refund_eligibility",
                    {"order_id": order_id},
                    result
                )
            )

            if result.get("success"):
                response = (
                    "Your order is eligible for a refund request. "
                    "Would you like me to submit one? Please also tell "
                    "me the reason for your refund."
                    if result.get("eligible")
                    else f"Unfortunately, your order isn't eligible. "
                         f"{result.get('reason')}"
                )
            else:
                response = result.get("error", "I couldn't check eligibility.")

            return _build_response(
                conversation_id,
                response,
                tool_calls,
                "deterministic"
            )

        reason = _extract_refund_reason(user_history)

        if not reason:
            return _build_response(
                conversation_id,
                "I can help submit a refund request. "
                "Could you tell me why you'd like to return the item?",
                [],
                "deterministic"
            )

        eligibility = _execute_tool(
            "check_refund_eligibility",
            {"order_id": order_id},
            user_history
        )

        tool_calls.append(
            _build_tool_trace(
                "check_refund_eligibility",
                {"order_id": order_id},
                eligibility
            )
        )

        if not eligibility.get("success") or not eligibility.get("eligible"):
            return _build_response(
                conversation_id,
                "I couldn't submit the refund request. "
                + eligibility.get("reason", eligibility.get("error", "")),
                tool_calls,
                "deterministic"
            )

        result = _execute_tool(
            "process_refund",
            {
                "order_id": order_id,
                "reason": reason
            },
            user_history
        )

        tool_calls.append(
            _build_tool_trace(
                "process_refund",
                {"order_id": order_id, "reason": reason},
                result
            )
        )

        if result.get("success"):
            request = result["refund_request"]

            response = (
                f"Your simulated refund request has been submitted. "
                f"Reference: {request['request_id']}. "
                "No actual payment has been refunded."
            )
        else:
            response = result.get("error", "I couldn't submit your request.")

        return _build_response(
            conversation_id,
            response,
            tool_calls,
            "deterministic"
        )

    # 4. Refund eligibility question
    if any(keyword in text for keyword in ["eligible", "qualify", "return"]):
        result = _execute_tool(
            "check_refund_eligibility",
            {"order_id": order_id},
            user_history
        )

        tool_calls.append(
            _build_tool_trace(
                "check_refund_eligibility",
                {"order_id": order_id},
                result
            )
        )

        response = (
            (
                "Your order is eligible for a refund request. "
                if result.get("eligible")
                else "Your order is not eligible for a refund request. "
            ) + result.get("reason", "")
            if result.get("success")
            else result.get("error", "Unable to check eligibility.")
        )

        return _build_response(
            conversation_id,
            response,
            tool_calls,
            "deterministic"
        )

    # 5. Delivery tracking
    if any(
        keyword in text
        for keyword in [
            "track", "tracking", "delivery",
            "package", "shipment", "where is",
            "arrive", "arriving"
        ]
    ):
        result = _execute_tool(
            "track_delivery",
            {"order_id": order_id},
            user_history
        )

        tool_calls.append(
            _build_tool_trace(
                "track_delivery",
                {"order_id": order_id},
                result
            )
        )

        if result.get("success"):
            response = (
                f"Your package is currently {result['delivery_status']} "
                f"at {result['current_location']}. "
            )

            if result.get("estimated_delivery"):
                response += (
                    f"Estimated delivery: {result['estimated_delivery']}."
                )
            else:
                response += "The package has already been delivered."
        else:
            response = result.get("error", "Unable to track your delivery.")

        return _build_response(
            conversation_id,
            response,
            tool_calls,
            "deterministic"
        )

    # 6. General order lookup
    if any(
        keyword in text
        for keyword in ["order", "items", "purchased", "bought", "status"]
    ):
        result = _execute_tool(
            "get_order",
            {"order_id": order_id},
            user_history
        )

        tool_calls.append(
            _build_tool_trace(
                "get_order",
                {"order_id": order_id},
                result
            )
        )

        if result.get("success"):
            order = result["order"]
            items = ", ".join(
                item["name"] for item in order["items"]
            )

            response = (
                f"Order #{order_id} is currently {order['status']}. "
                f"Your items: {items}."
            )
        else:
            response = result.get("error", "Unable to retrieve your order.")

        return _build_response(
            conversation_id,
            response,
            tool_calls,
            "deterministic"
        )

    # 7. Unsupported or unclear requests
    return _build_response(
        conversation_id,
        "I'm not sure how to help with that request. "
        "I can assist with orders, delivery tracking and refunds, "
        "or connect you with human support.",
        [],
        "deterministic"
    )


# --------------------------------------------------
# OPENAI AGENT
# --------------------------------------------------

def _run_openai_agent(
    conversation_id,
    message,
    history
):
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": message}
    ]

    user_history = _get_user_history(
        history + [{"role": "user", "content": message}]
    )

    tool_calls = []

    for _ in range(MAX_TOOL_ITERATIONS):

        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=OPENAI_TOOLS,
            tool_choice="auto",
            temperature=0.2
        )

        assistant_message = completion.choices[0].message

        messages.append(
            assistant_message.model_dump(exclude_none=True)
        )

        # Model has produced a final response.
        if not assistant_message.tool_calls:
            response = assistant_message.content or (
                "I'm sorry, I couldn't generate a response."
            )

            CONVERSATIONS[conversation_id] = messages[1:]

            escalated_call = next(
                (
                    call for call in tool_calls
                    if call["tool"] == "escalate_to_human"
                    and call["result"].get("success")
                ),
                None
            )

            ticket_id = (
                escalated_call["result"]["ticket"]["ticket_id"]
                if escalated_call else None
            )

            return _build_response(
                conversation_id,
                response,
                tool_calls,
                "openai",
                escalated=bool(ticket_id),
                ticket_id=ticket_id
            )

        # Execute each requested function.
        for tool_call in assistant_message.tool_calls:

            name = tool_call.function.name

            try:
                arguments = json.loads(
                    tool_call.function.arguments
                )
            except (json.JSONDecodeError, TypeError):
                arguments = None

            result = _execute_tool(
                name,
                arguments,
                user_history
            )

            tool_calls.append(
                _build_tool_trace(name, arguments, result)
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str)
            })

    # Prevent unlimited agent loops.
    CONVERSATIONS[conversation_id] = messages[1:]

    return _build_response(
        conversation_id,
        "I've reached the maximum number of tool operations. "
        "Please clarify your request or contact human support.",
        tool_calls,
        "openai"
    )


# --------------------------------------------------
# PUBLIC AGENT ENTRY POINT
# --------------------------------------------------

def handle_message(message, conversation_id=None):
    """Process a customer message and return a structured response."""

    message = message.strip()

    if not message:
        raise ValueError("Message cannot be empty.")

    conversation_id = conversation_id or str(uuid4())

    history = CONVERSATIONS.get(conversation_id, [])

    mode = get_agent_mode()

    if mode == "openai":
        try:
            return _run_openai_agent(
                conversation_id,
                message,
                history
            )

        except Exception as exc:
            # Log the error for debugging purposes.
            print(f"\nOPENAI AGENT ERROR: {type(exc).__name__}: {exc}\n")

            return _build_response(
                conversation_id,
                "I'm temporarily unable to access the AI service. "
                "Please try again shortly.",
                [],
                "openai"
            )

    # Deterministic fallback.
    result = _run_deterministic_agent(
        conversation_id,
        message,
        history
    )

    CONVERSATIONS[conversation_id] = (
        history
        + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": result["response"]}
        ]
    )

    return result
