# SupportFlow AI

A lightweight AI-powered customer support assistant built with **Python, FastAPI, and JavaScript**. It demonstrates how an agent can interact with business tools to retrieve order information, track deliveries, check refund eligibility, create simulated refund requests, and escalate conversations to human support.

## Features

- **Order lookup** — retrieve customer order details.
- **Delivery tracking** — check delivery status, carrier, current location, and estimated delivery.
- **Refund eligibility** — evaluate refund requests against a 30-day policy.
- **Refund requests** — create simulated requests with duplicate-submission protection. No real payment is processed.
- **Human escalation** — create support tickets for cases requiring human assistance.
- **Conversation context** — retain conversation history and resolve follow-up questions.
- **Agent activity** — inspect the tools executed by the agent through the interface.

## Architecture

```text
Customer
   |
   v
Web interface (HTML, CSS, JavaScript)
   |
   v
FastAPI backend
   |
   v
Agent orchestration
   |
   +---- OpenAI function calling (optional)
   |
   +---- Deterministic fallback
   |
   v
Business tools
   |
   +---- Order lookup
   +---- Delivery tracking
   +---- Refund eligibility and requests
   +---- Human support escalation
   |
   v
In-memory sample data
```

## Technology stack

- Python
- FastAPI
- OpenAI Python SDK
- Pydantic
- JavaScript, HTML, CSS
- Pytest

## Running locally

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/supportflow-ai.git
cd supportflow-ai
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local `.env` file:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

An API key is required to use the OpenAI-powered agent. Without a configured key, the application uses its deterministic fallback.

### 5. Start the application

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

API health check: http://127.0.0.1:8000/api/health

## Running tests

```bash
python -m pytest -v
```

## Sample scenarios

The application includes sample orders:

| Order | Status | Example |
|---|---|---|
| 1042 | Delivered | Refund eligibility |
| 1043 | Delivered | Outside the refund window |
| 1044 | In transit | Delivery tracking |

Try asking the assistant to track order 1044, check refund eligibility for order 1042, or request human assistance for suspected fraudulent activity.

## Implementation notes

The OpenAI function-calling integration is implemented, with a deterministic fallback available when no API key is configured. The deterministic mode uses rule-based routing and the same business tools.

Sample data, conversations, refund requests, and support tickets are stored in memory and reset when the application restarts. Refund requests and support tickets are simulated; no external payment or ticketing system is connected.

This project is a compact demonstration of agent orchestration and tool integration, not a production-ready customer support system.
