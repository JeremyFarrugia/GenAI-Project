var outputDiv;
var promptInput;
var promptHistory = [];
var promptHistoryIndex = 0;
var user = 'Guest'; // The user's name (temporary)
var chatID = 1; // The chat ID
var canPrompt = false; // Whether the user can prompt the model or not
var loggedIn = false; // Whether the user is logged in or not

var loginModal;
var loginButton;
var registerButton;

var registerModal;
var registerButton;

var accountModal;

document.addEventListener("DOMContentLoaded", async function (event) {
    outputDiv = document.getElementById('output');
    promptInput = document.getElementById('prompt-input');

    loginModal = document.getElementById('loginModal');
    registerModal = document.getElementById('registerModal');
    accountModal = document.getElementById('accountModal');

    promptInput.addEventListener
    // Execute the prompt when the user presses Enter
    promptInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') executePrompt();
    });

    // Check if the user is logged in
    await checkSession();

    await getChatID();

    // Handle login form submission
    document.getElementById('loginForm').onsubmit = async (event) => {
        attemptLogin(event);
    };

    // Handle register form submission
    document.getElementById('registerForm').onsubmit = async (event) => {
        createUser(event);
    }

    // Could remove - button up/down to retrieve previous prompts
    promptInput.addEventListener('keydown', (e) => {
        handlePromptKeydown(e);
    });

    // Audio button
    document.getElementById('output').addEventListener('click', function(event) {
        // Check if the clicked element is the audio button
        if (event.target && (event.target.matches('button.audio-button') || event.target.matches('img.audio-icon'))) {
            // Access the parent div of the clicked button
            const parentDiv = event.target.closest('.model-response-container');
            playAudio(parentDiv);
        }
    });

    // Focus on the input field
    promptInput.focus();
});

function openLogin() {
    loginModal.style.display = 'block';
}

function closeLogin() {
    loginModal.style.display = 'none';
}

function swapLoginButton() {
    loginButton = document.getElementById('login-button');
    userButton = document.getElementById('user-button');
    loginButton.style.display = 'none';
    userButton.style.display = 'block';
}

function switchToRegisterModal() {
    loginModal.style.display = 'none';
    registerModal.style.display = 'block';
}

function switchToLoginModal() {
    registerModal.style.display = 'none';
    loginModal.style.display = 'block';
}

function closeRegister() {
    registerModal.style.display = 'none';
}

function changeUser() {
    closeDetails();
    openLogin();
}

function openDetails() {
    accountModal.style.display = 'block';
}

function closeDetails() {
    accountModal.style.display = 'none';
}

function loginSuccess(username) {
    loggedIn = true;
    user = username;

    // Update the user's account details
    document.getElementById('accountUsername').innerText = user;

    // Update the account details button
    document.getElementById('user-button').innerText = user;


    swapLoginButton();
    getChatID();
}

async function checkSession() {
    try {
        const response = await fetch('/session-status', {
            method: 'GET',
            credentials: 'include' // Include session cookies
        });

        const result = await response.json();

        if (result.loggedIn) {
            console.log(`User is logged in as: ${result.user}`);
            loginSuccess(result.user);
        } else {
            console.log('User is not logged in.');
            // UI is already set up
        }
    } catch (error) {
        console.error('Error checking session status:', error);
    }
}

async function attemptLogin(event) {
    event.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        const result = await response.json();
        if (response.ok) {
            alert(result.message);
            loginModal.style.display = 'none'; // Close login modal on successful login

            loginSuccess(username);
        } else {
            console.error('Error logging in:', result.error);
            alert(result.error);
        }
    } catch (error) {
        console.error('Error logging in:', error);
        alert('An error occurred.');
    }
}

async function createUser(event) {
    event.preventDefault();
    const username = document.getElementById('register-username').value;
    const password = document.getElementById('register-password').value;

    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        const result = await response.json();
        if (response.ok) {
            alert(result.message);
            registerModal.style.display = 'none'; // Close registration modal on successful login

            loginSuccess(username);
        } else {
            console.error('Error creating user:', result.error);
            alert(result.error);
        }
    } catch (error) {
        console.error('Error creating user:', error);
        alert('An error occurred.');
    }
}

function handlePromptKeydown(e) {
    if (e.key === 'ArrowUp') {
        console.log('Trying to retrieve previous prompt');
        promptHistoryIndex += 1;
        promptHistoryIndex = Math.min(promptHistoryIndex, promptHistory.length); //
        promptHistoryIndex = Math.max(promptHistoryIndex, 0);
        console.log(promptHistoryIndex);
        let previousPrompt = promptHistory[promptHistory.length - promptHistoryIndex];
        
        console.log(previousPrompt);
        

        if (previousPrompt === undefined) return;
        promptInput.value = previousPrompt;

        // Move the cursor to the end of the input
        promptInput.setSelectionRange(promptInput.value.length, promptInput.value.length);
    }
    else if (e.key === 'ArrowDown') {
        console.log('Trying to retrieve next prompt');
        promptHistoryIndex -= 1;
        promptHistoryIndex = Math.max(promptHistoryIndex, 0); // Ensure the index is not negative
        promptHistoryIndex = Math.min(promptHistoryIndex, promptHistory.length); // Ensure the index is not greater than the length of the history
        console.log(promptHistoryIndex);
        let nextPrompt = promptHistory[promptHistory.length - promptHistoryIndex];
        console.log(nextPrompt);

        if (nextPrompt === undefined) return;
        promptInput.value = nextPrompt;

        // Move the cursor to the end of the input
        promptInput.setSelectionRange(promptInput.value.length, promptInput.value.length);
    }
}

async function getChatID() {
    if (!loggedIn) {
        outputDiv.innerHTML += `<p style="color: red;" class = model-error>You must be logged in to chat.</p>`;
        return;
    }
    try {
        const response = await fetch('/chat-id', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: user
            })
        });

        const result = await response.json();

        if (response.ok) {
            chatID = result.chatID;
            console.log('Chat ID:', chatID);
            canPrompt = true;
        } else {
            console.error('Error getting chat ID (response failure):', result.error);
            outputDiv.innerHTML += `<p style="color: red;" class = model-error>Error: ${result.error}</p>`;
        }
    } catch (error) {
        console.error('Error getting chat ID (system error):', error);
        outputDiv.innerHTML += `<p style="color: red;" class = model-error>Error: ${error}</p>`;
    }
}

async function executePrompt() {
    if (!loggedIn) {
        alert('Please log in to prompt the model.');
        return;
    }

    if (!canPrompt) {
        outputDiv.innerHTML += `<p style="color: red;" class = model-error>Error: You cannot prompt the model yet. Please wait a few seconds and try again.</p>`;
        return;
    }

    const prompt = promptInput.value.trim();
    console.log('prompt entered: ' + prompt);
    if (!prompt) return;

    console.log(prompt);
    console.log(promptHistory);

    if (promptHistory.length === 0 || promptHistory[promptHistory.length - 1] !== prompt) {
        promptHistory.push(prompt);
    }

    promptHistoryIndex = 0;

    promptInput.value = '';

    // Display the prompt in the output
    outputDiv.innerHTML += `
        <div class="user-prompt-container text-container">
            <p style="color: #00ff00;" class = user-prompt>${user}> ${prompt}</p>
        </div>
    `;

    try {
        const response = await fetch('/prompt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt
            })
        });

        const result = await response.json();

        if (result.success) {
            if (result.reply) {
                outputDiv.innerHTML += `
                    <div class="model-response-container text-container">
                        <p class=model-response>The Rizzler > ${result.reply}</p>
                        <button class="audio-button">
                            <img src="${audioIconUrl}" alt="Play audio" class="audio-icon">
                        </button>
                    </div>
                `;
            }
        } else {
            outputDiv.innerHTML += `<p style="color: red;" class = model-error>Error: ${result.error}</p>`;
        }
    } catch (error) {
        outputDiv.innerHTML += `<p style="color: red;" class = model-error>Error: ${error}</p>`;
    }

    // Scroll to the bottom and clear the input
    window.scrollTo(0, document.body.scrollHeight);
    promptInput.value = '';
}

async function playAudio(parentDiv) {
    stopAudio(); // This doesn't work :)
    if (isAudioPlaying()) { // Neither does this
        alert('An audio is already playing.');
        return;
    }

    // Get the model response text
    const modelResponse = parentDiv.getElementsByClassName('model-response')[0];
    const modelResponses = document.getElementsByClassName('model-response');
    //const modelResponses = document.getElementsByClassName('model-response');
    //const lastModelResponse = modelResponses[modelResponses.length - 1];

    // find the index of the selected model response
    const index = Array.from(modelResponses).indexOf(modelResponse);

    console.log('index: ' + index);
    

    try {
        const response = await fetch('/generate-audio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: modelResponse.innerText,
                username: user,
                chatID: chatID,
                index: index,
            })
        });

        if(!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        audio.play();
    }
    catch (error) {
        outputDiv.innerHTML += `<p style="color: red;" class = model-error>Error: ${error}</p>`;
    }
}

function isAudioPlaying() {
    const audio = document.getElementsByTagName('audio')[0];
    return audio && !audio.paused;
}

function stopAudio() {
    // Stop all audio elements
    const audioElements = document.getElementsByTagName('audio');
    for (let audio of audioElements) {
        audio.pause();
    }
}