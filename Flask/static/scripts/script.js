var outputDiv;
var promptInput;
var promptHistory = [];
var promptHistoryIndex = 0;
var user = 'User'; // The user's name (temporary)
var loggedIn = false; // Whether the user is logged in or not
var generatingAudio = false; //
var generatingStory = false; // Prevent multiple story generations at once

var audio = new Audio();

var loginModal;
var loginButton;
var registerButton;

var registerModal;
var registerButton;

var accountModal;

var generated = []; // Used to avoid generating the same audio multiple times

// TODO - Organise into sub-scripts

const socket = io();

document.addEventListener("DOMContentLoaded", async function (event) {
    outputDiv = document.getElementById('output');
    promptInput = document.getElementById('prompt-input');

    loginModal = document.getElementById('loginModal');
    registerModal = document.getElementById('registerModal');
    accountModal = document.getElementById('accountModal');

    if (promptInput === null) {
        console.log('Could not find the prompt input element. but don\'t worry You\'re probably on a different page.');
    }
    else {
        // Execute the prompt when the user presses Enter
        promptInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') executePrompt();
        });

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
            else if (event.target && event.target.matches('button.generate-button')) {
                // Access the parent div of the clicked button
                const parentDiv = event.target.closest('.model-response-container');
                
                generateStory(parentDiv);
            }
        });

        // Focus on the input field
        promptInput.focus();
    }

    // Check if the user is logged in
    await checkSession();

    // Handle login form submission
    document.getElementById('loginForm').onsubmit = async (event) => {
        attemptLogin(event);
    };

    // Handle register form submission
    document.getElementById('registerForm').onsubmit = async (event) => {
        createUser(event);
    }
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
    if (loginButton.style.display === 'none') {
        loginButton.style.display = 'block';
        userButton.style.display = 'none';
    } else {
        loginButton.style.display = 'none';
        userButton.style.display = 'block';
    }
    /*loginButton.style.display = 'none';
    userButton.style.display = 'block';*/
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

async function loginSuccess(username, setCookie = false) {
    loggedIn = true;
    user = username;

    // Update the user's account details
    document.getElementById('accountUsername').innerText = user;

    // Update the account details button
    document.getElementById('user-button').innerText = user;

    if (setCookie) {
        try {
            const response = await fetch('/set-login-cookie', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                })
            });
    
            const result = await response.json();
            if (response.ok) {
                console.log('Cookie set:', result.message);
            } else {
                console.error('Error setting cookie:', result.error);
            }
        } catch (error) {
            console.error('Error setting cookie:', error);
        }
    }


    swapLoginButton();
}

async function checkSession() {
    /*try { // Deprecated, using cookies instead
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
    }*/
    
        try {
            const response = await fetch('/login-status', {
                method: 'GET',
                credentials: 'include' // Include session cookies
            });
    
            const result = await response.json();
    
            if (result.logged_in) {
                console.log(`User is logged in as: ${result.user}`);
                loginSuccess(result.user, setCookie = false);
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

            loginSuccess(username, setCookie = true);
        } else {
            console.error('Error logging in:', result.error);
            alert(result.error);
        }
    } catch (error) {
        console.error('Error logging in:', error);
        alert('An error occurred.');
    }
}

async function logout() {
    try {
        const response = await fetch('/logout', {
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
            // Close the account details modal
            closeDetails();

            console.log(result.message);
            loggedIn = false;

            swapLoginButton();

            // Clear the user's account details
            document.getElementById('accountUsername').innerText = 'User';
            
            // Clear the account details button
            document.getElementById('user-button').innerText = 'User';

            outputDiv.innerHTML = ''; // Clear the chat history
        }
    }
    catch (error) {
        console.error('Error logging out:', error);
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

            loginSuccess(username, setCookie = true);
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

async function executePrompt() {
    if (!loggedIn) {
        alert('Please log in to prompt the model.');
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
            <div class="chat-container-inner">
                <h3 class="user-prompt-header">${user}</h3>
                <p style="color: #00ff00;" class = user-prompt>${prompt}</p>
            </div>
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
                        <div class="chat-container-inner">
                            <h3 class="model-response-header">Dino</h3>
                            <p class=model-response>${result.reply}</p>
                            <button class="generate-button"> Create Story </button>
                        </div>
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

async function generateStory(parentDiv) {
    if (generatingStory) {
        console.log('Already generating a story, please wait.');
        return;
    }

    generatingStory = true;

    

    const data = {
        content: parentDiv.getElementsByClassName('model-response')[0].innerText,
        username: user
    };

    socket.emit('generate-story', data);

}

socket.on('story-progress', (data) => {
    outputDiv.innerHTML += `<p>${data.message}</p>`;
});

socket.on('story-error', (data) => {
    outputDiv.innerHTML += `<p style="color: red;" class = model-error>Error: ${data.error}</p>`;
    generatingStory = false;
});

socket.on('story-complete', (data) => {
    outputDiv.innerHTML += `
        <p>${data.message}</p>
    `;

    generatingStory = false;

    outputDiv.innerHTML += `
        <p>Redirecting in...</p>
        <p>3</p>
    `;
    
    // Countdown to redirect
    let count = 3;
    const interval = setInterval(() => {
        count -= 1;
        outputDiv.lastElementChild.innerText = count;

        if (count === 0) {
            clearInterval(interval);
            window.location.href = `/stories-${user}`;
        }
    }, 1000);
    
});

async function playAudio(parentDiv) {
    stopAudio(); // This doesn't work :)
    if (isAudioPlaying()) { // Fixed this one though :)
        alert('Already playing audio. Please wait for the current audio to finish.');
        return;
    }


    if (generatingAudio) { // Prevent multiple audio generations at once (user spamming the button while waiting)
        console.log('Audio already being generated, ignoring button press.');
        return;
    }

    generatingAudio = true;

    // Get the model response text
    const modelResponse = parentDiv.getElementsByClassName('model-response')[0];
    const modelResponses = document.getElementsByClassName('model-response');
    //const modelResponses = document.getElementsByClassName('model-response');
    //const lastModelResponse = modelResponses[modelResponses.length - 1];

    // find the index of the selected model response
    const index = Array.from(modelResponses).indexOf(modelResponse);

    console.log('index: ' + index);

    shouldExist = false;

    // Check if the audio has already been generated
    if (generated.includes(index)) {
        console.log('Audio already generated');
        shouldExist = true;
    }
    else {
        console.log('Audio not generated yet');
    }
    

    try {
        const response = await fetch('/generate-tts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: modelResponse.innerText,
                username: user,
                index: index,
                alreadyGenerated: shouldExist,
            })
        });

        if(!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        generated.push(index);

        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        audio = new Audio(audioUrl);
        audio.play();

        // Get audio duration


    }
    catch (error) {
        outputDiv.innerHTML += `<p style="color: red;" class = model-error>Error: ${error}</p>`;
    }
    finally {
        generatingAudio = false;
    }
}

function isAudioPlaying() {
    console.log('audio.paused: ' + audio.paused);
    return !audio.paused;
}

function stopAudio() {
    // Stop all audio elements
    const audioElements = document.getElementsByTagName('audio');
    for (let audio of audioElements) {
        audio.pause();
    }
}
