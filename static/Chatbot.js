function toggleChat() {
    const chatWindow = document.getElementById("chatbotWindow");
    
    // Check if it's currently visible
    if (chatWindow.style.display === "none" || chatWindow.style.display === "") {
        chatWindow.style.display = "flex";  // Show chatbot
    } else {
        chatWindow.style.display = "none"; // Hide chatbot
    }
}

// Ensure chatbot is hidden on page load
document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("chatbotWindow").style.display = "none";
});

let chatHistory = [];

async function sendMessage() {
    const inputField = document.getElementById("chatInput");
    const message = inputField.value.trim();
    if (message === "") return;

    // Display user message
    displayMessage("You", message);
    inputField.value = "";

    // Show typing indicator
    displayMessage("Bot", "Typing...");

    setTimeout(async () => {
        // Remove typing indicator
        const chatMessages = document.getElementById("chatMessages");
        chatMessages.lastChild.remove();

        try {
            const response = await fetch("/ask_faq", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    question: message,
                    history: chatHistory // ✅ send conversation history
                })
            });

            const data = await response.json();
            const botReply = data.answer || "Sorry, I didn’t get that.";

            // Display bot message
            displayMessage("Bot", botReply);

            // ✅ Add this exchange to the memory
            chatHistory.push({ user: message, bot: botReply });
            
            // Save updated chat history to localStorage
            localStorage.setItem("chat_history", JSON.stringify(chatHistory));

        } catch (error) {
            console.error("Error fetching FAQ:", error);
            displayMessage("Bot", "Sorry, something went wrong.");
        }
    }, 1000); // Simulated delay
}


function handleKeyPress(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
}

function displayMessage(sender, text) {
    const chatMessages = document.getElementById("chatMessages");
    const messageElement = document.createElement("p");
    messageElement.classList.add(sender === "You" ? "user-message" : "bot-message");
    messageElement.textContent = `${sender}: ${text}`;
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    saveChatHistory();
}


function makeDraggable() {
    const chatWindow = document.getElementById("chatbotWindow");
    const chatHeader = document.querySelector(".chat-header"); // Only drag from header
    let isDragging = false, startX, startY, startLeft, startTop;

    chatHeader.style.cursor = "grab"; // Set grab cursor for header
    chatHeader.addEventListener("mousedown", (e) => {
        if (e.target.tagName === "BUTTON") return; // Prevent dragging if clicking buttons
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        startLeft = chatWindow.offsetLeft;
        startTop = chatWindow.offsetTop;
        chatHeader.style.cursor = "grabbing";
        e.preventDefault();
    });

    document.addEventListener("mousemove", (e) => {
        if (!isDragging) return;

        let newLeft = startLeft + (e.clientX - startX);
        let newTop = startTop + (e.clientY - startY);

        // Prevent moving out of screen bounds
        newLeft = Math.max(0, Math.min(window.innerWidth - chatWindow.clientWidth, newLeft));
        newTop = Math.max(0, Math.min(window.innerHeight - chatWindow.clientHeight, newTop));

        chatWindow.style.left = `${newLeft}px`;
        chatWindow.style.top = `${newTop}px`;
    });

    document.addEventListener("mouseup", () => {
        isDragging = false;
        chatHeader.style.cursor = "grab";
    });
}
makeDraggable();


function saveChatHistory() {
    localStorage.setItem("chat_history", JSON.stringify(chatHistory));
}

function getLoggedInUser() {
    return typeof LOGGED_IN_USER !== "undefined" ? LOGGED_IN_USER : "guest";
}
function loadChatHistory() {
    const loggedInUser = getLoggedInUser();
    const storedUser = localStorage.getItem("current_user");

    if (storedUser !== loggedInUser) {
        localStorage.removeItem("chat_history");
        localStorage.setItem("current_user", loggedInUser);
        chatHistory = [];
        return;
    }

    const savedHistory = localStorage.getItem("chat_history");
    if (savedHistory) {
        chatHistory = JSON.parse(savedHistory);

        // Re-render all messages using displayMessage
        chatHistory.forEach(turn => {
            displayMessage("You", turn.user);
            displayMessage("Bot", turn.bot);
        });
    }
}

document.addEventListener("DOMContentLoaded", loadChatHistory);

function clearChatbotHistory() {
    localStorage.removeItem("chat_history");
    localStorage.removeItem("current_user");
  }

