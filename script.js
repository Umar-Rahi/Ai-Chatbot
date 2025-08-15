document.addEventListener("DOMContentLoaded", function() {
    var chatlog = document.getElementById("chatlog");
    var userInput = document.getElementById("userInput");
    var sendButton = document.getElementById("sendButton");

    // Define a dictionary of possible user inputs and corresponding bot responses
    var botResponses = {
        "hello": ["Hello!", "Hi there!", "Greetings!"],
        "how are you": ["I'm good, thanks!", "I'm doing well!", "All is well!"],
        "what is your name": ["I'm an AI chatbot.", "You can call me Chatbot.", "I don't have a name."],
        "okk bye": ["Goodbye!", "Farewell!", "Take care!"],
        "do you know me":["of course i know your name is Ashfiya Naaz you're one of my favorite people to chat with"],
        "top 5 college in dehradun":["1. Graphic Era University "+
        "2. Petroleum Energy Studies 3. Doon University 4. DIT University Uttaranchal University"],
        "tell me about graphic era":["Graphic Era University (GEU) is a private university located in Dehradun, Uttarakhand, India. It was established in 1993 as Graphic Era Institute of Technology and was later granted university status in 2008. The university is affiliated with the University Grants Commission (UGC) and offers a wide range of undergraduate, postgraduate, and doctoral programs across various disciplines."]

    };

    // Function to generate a response from the bot
    function generateResponse(userInput) {
        userInput = userInput.toLowerCase();

        if (userInput in botResponses) {
            var responses = botResponses[userInput];
            return responses[Math.floor(Math.random() * responses.length)];
        } else {
            return "I'm sorry, I don't understand.";
        }
    }

    // Function to add a message to the chatlog
    function addMessage(message, sender) {
        var messageDiv = document.createElement("div");
        messageDiv.className = "message " + sender;
        messageDiv.textContent = message;

        chatlog.appendChild(messageDiv);
        chatlog.scrollTop = chatlog.scrollHeight;
    }

    // Function to handle user input and generate bot response
    function processInput() {
        var inputText = userInput.value.trim();

        if (inputText !== "") {
            addMessage(inputText, "user");

            var response = generateResponse(inputText);
            addMessage(response, "bot");

            userInput.value = "";
        }
    }

    // Event listener for send button click
    sendButton.addEventListener("click", function() {
        processInput();
    });

    // Event listener for Enter key press
    userInput.addEventListener
    ("keyup", function(event) {
        if (event.keyCode === 13) {
            processInput();
        }
    });
});