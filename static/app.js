
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const messagesContainer = document.getElementById("messages");
const sendButton = document.getElementById("send-button");
const newChatButton = document.getElementById("new-chat-button");
const activityContainer = document.getElementById("agent-activity");
const conversationLabel = document.getElementById("conversation-label");
const agentModeLabel = document.getElementById("agent-mode");
const suggestionsContainer = document.getElementById("suggestions");

let conversationId = null;
let isLoading = false;


// ---------- DOM helpers ----------

function createElement(tag, className, text = "") {
    const element = document.createElement(tag);

    if (className) {
        element.className = className;
    }

    if (text) {
        element.textContent = text;
    }

    return element;
}


function getCurrentTime() {
    return new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
    });
}


function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}


// ---------- Chat rendering ----------

function addMessage(role, text, options = {}) {
    const isUser = role === "user";

    const row = createElement(
        "div",
        `message-row ${isUser ? "user-row" : "agent-row"}`
    );

    const avatar = createElement(
        "div",
        `message-avatar ${isUser ? "user-avatar" : "agent-avatar"}`,
        isUser ? "AM" : "S"
    );

    const content = createElement("div", "message-content");

    const author = createElement("div", "message-author");
    author.textContent = isUser ? "Alex Morgan" : "SupportFlow AI";

    const timestamp = createElement("span", "", options.timestamp || getCurrentTime());
    author.appendChild(timestamp);

    const bubble = createElement(
        "div",
        `message-bubble ${isUser ? "user-bubble" : "agent-bubble"}`
    );

    bubble.textContent = text;

    if (options.error) {
        bubble.classList.add("error-bubble");
    }

    content.appendChild(author);
    content.appendChild(bubble);

    row.appendChild(avatar);
    row.appendChild(content);

    messagesContainer.appendChild(row);

    scrollToBottom();

    return row;
}


function showTypingIndicator() {
    const row = createElement("div", "message-row agent-row");
    row.id = "typing-indicator";

    const avatar = createElement(
        "div",
        "message-avatar agent-avatar",
        "S"
    );

    const content = createElement("div", "message-content");

    const author = createElement("div", "message-author");
    author.textContent = "SupportFlow AI";

    const bubble = createElement("div", "message-bubble agent-bubble");
    const dots = createElement("div", "typing-indicator");

    for (let i = 0; i < 3; i++) {
        dots.appendChild(createElement("span"));
    }

    bubble.appendChild(dots);
    content.appendChild(author);
    content.appendChild(bubble);

    row.appendChild(avatar);
    row.appendChild(content);

    messagesContainer.appendChild(row);

    scrollToBottom();
}


function removeTypingIndicator() {
    document.getElementById("typing-indicator")?.remove();
}


// ---------- Agent activity ----------

function clearActivity() {
    activityContainer.replaceChildren();

    const empty = createElement("div", "activity-empty");
    empty.appendChild(createElement("div", "activity-empty-icon", "⌘"));
    empty.appendChild(createElement("div", "", "No tools executed yet"));
    empty.appendChild(
        createElement("span", "", "Agent actions will appear here")
    );

    activityContainer.appendChild(empty);
}


function renderToolCalls(toolCalls) {
    if (!toolCalls || toolCalls.length === 0) {
        return;
    }

    activityContainer.replaceChildren();

    toolCalls.forEach((call) => {
        const item = createElement("div", "activity-item");

        const heading = createElement("div", "activity-tool");

        heading.appendChild(
            createElement("span", "", call.tool)
        );

        const success = call.result?.success === false
            ? "CHECK"
            : "EXECUTED";

        const status = createElement(
            "span",
            "tool-success",
            success
        );

        if (success === "CHECK") {
            status.style.color = "var(--orange)";
        }

        heading.appendChild(status);

        const argumentsElement = createElement(
            "div",
            "tool-arguments"
        );

        argumentsElement.textContent =
            "INPUT  " + JSON.stringify(call.arguments ?? {});

        const resultElement = createElement(
            "div",
            "tool-result"
        );

        resultElement.textContent =
            "OUTPUT " + JSON.stringify(call.result ?? {});

        item.appendChild(heading);
        item.appendChild(argumentsElement);
        item.appendChild(resultElement);

        activityContainer.appendChild(item);
    });
}


// ---------- Backend communication ----------

async function checkBackend() {
    try {
        const response = await fetch("/api/health");

        if (!response.ok) {
            throw new Error("Backend health check failed");
        }

        const data = await response.json();

        updateAgentMode(data.agent_mode);

    } catch (error) {
        agentModeLabel.textContent = "Backend unavailable";
        agentModeLabel.style.color = "var(--red)";
        console.error("Backend connection error:", error);
    }
}


function updateAgentMode(mode) {
    const labels = {
        openai: "OpenAI tool-calling",
        deterministic: "Deterministic fallback"
    };

    agentModeLabel.textContent = labels[mode] || mode || "Unknown";
}


async function sendMessage(message) {
    if (isLoading || !message.trim()) {
        return;
    }

    isLoading = true;
    sendButton.disabled = true;
    messageInput.disabled = true;

    suggestionsContainer?.remove();

    addMessage("user", message);

    messageInput.value = "";
    messageInput.style.height = "auto";

    showTypingIndicator();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                conversation_id: conversationId
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "The server could not process your message."
            );
        }

        // Preserve the conversation for subsequent messages.
        conversationId = data.conversation_id;

        conversationLabel.textContent =
            conversationId.slice(0, 8).toUpperCase();

        updateAgentMode(data.agent_mode);

        removeTypingIndicator();

        addMessage("assistant", data.response);

        renderToolCalls(data.tool_calls);

        if (data.escalated) {
            addMessage(
                "assistant",
                data.ticket_id
                    ? `This conversation has been escalated to human support. Ticket reference: ${data.ticket_id}.`
                    : "This conversation has been escalated to human support."
            );
        }

    } catch (error) {
        removeTypingIndicator();

        addMessage(
            "assistant",
            error.message || "Something went wrong. Please try again.",
            { error: true }
        );

        console.error("Chat request failed:", error);

    } finally {
        isLoading = false;
        sendButton.disabled = false;
        messageInput.disabled = false;
        messageInput.focus();
        scrollToBottom();
    }
}


// ---------- Event listeners ----------

chatForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const message = messageInput.value.trim();

    if (message) {
        sendMessage(message);
    }
});


messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatForm.requestSubmit();
    }
});


messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";

    messageInput.style.height =
        Math.min(messageInput.scrollHeight, 120) + "px";
});


document.querySelectorAll(".suggestion").forEach((button) => {
    button.addEventListener("click", () => {
        const message = button.dataset.message;

        if (message) {
            sendMessage(message);
        }
    });
});


newChatButton.addEventListener("click", () => {
    conversationId = null;

    messagesContainer.replaceChildren();

    const divider = createElement("div", "date-divider");
    divider.appendChild(createElement("span", "", "TODAY"));
    messagesContainer.appendChild(divider);

    addMessage(
        "assistant",
        "Hi Alex! I'm your AI support assistant. I can help you track orders, check refund eligibility, and resolve delivery issues. What can I help you with today?"
    );

    conversationLabel.textContent = "NEW SESSION";

    clearActivity();
    checkBackend();

    messageInput.focus();
});


// ---------- Initialize ----------

clearActivity();
checkBackend();
