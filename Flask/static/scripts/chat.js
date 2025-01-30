var outputDiv;
var promptInput;
var promptHistory = [];
var promptHistoryIndex = 0;
var generatingAudio = false; //
var generatingStory = false; // Prevent multiple story generations at once
var generatingImage = false
var imagesGenerated = []; // avoid generating multiple images for the same response
let pendingImageGenerations = new Map();

var audio = new Audio();

var generated = []; // Used to avoid generating the same audio multiple times

const socket = io();

document.addEventListener("DOMContentLoaded", async function (event) {
    outputDiv = document.getElementById('output');
    promptInput = document.getElementById('prompt-input');

    await userOnPageLoad();

    setupPrompt();
});

function setupPrompt() {
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

    // Create response container
    const responseIndex = document.getElementsByClassName('model-response').length;
    const responseContainer = document.createElement('div');
    responseContainer.className = 'model-response-container text-container';
    responseContainer.innerHTML = `
        <div class="chat-container-inner">
            <h3 class="model-response-header">Dino</h3>
            <p class="model-response"></p>
            <button class="generate-button">Create Story</button>
        </div>
        <button class="audio-button">
            <img src="${audioIconUrl}" alt="Play audio" class="audio-icon">
        </button>
    `;

    outputDiv.appendChild(responseContainer);

    try {
        // Get model response first
        const response = await fetch('/prompt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prompt })
        });

        const result = await response.json();

        if (result.success && result.reply) {
            // Update the response text
            const modelResponse = responseContainer.querySelector('.model-response');
            modelResponse.textContent = result.reply;

            // Now add the image container and start image generation
            const chatContainer = responseContainer.querySelector('.chat-container-inner');
            const imageContainer = document.createElement('div');
            imageContainer.className = 'story-image-container';
            imageContainer.innerHTML = '<div class="image-loading">Generating image...</div>';

            // Insert image container before the create story button
            const generateButton = responseContainer.querySelector('.generate-button');
            chatContainer.insertBefore(imageContainer, generateButton);

            // Start image generation after text is loaded
            const imageGenPromise = generateImage(responseContainer, responseIndex);
            pendingImageGenerations.set(responseIndex, imageGenPromise);

            // Wait for image generation to complete
            await imageGenPromise;
            pendingImageGenerations.delete(responseIndex);
        } else {
            outputDiv.innerHTML += `<p style="color: red;" class="model-error">Error: ${result.error}</p>`;
        }
    } catch (error) {
        outputDiv.innerHTML += `<p style="color: red;" class="model-error">Error: ${error}</p>`;
    }

    window.scrollTo(0, document.body.scrollHeight);
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
            window.location.href = data.url;
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

async function generateImage(parentDiv, index) {
    if (generatingImage || imagesGenerated.includes(index)) {
        console.log('Image already being generated.');
        return;
    }
    generatingImage = true;

    const imageContainer = parentDiv.querySelector('.story-image-container');
    const loadingDiv = imageContainer.querySelector('.image-loading');

    try {
        const modelResponse = parentDiv.getElementsByClassName('model-response')[0];
        const lines = modelResponse.innerText.split('\n').filter(line => line.trim());

        // Get title and first sentence
        const title = lines[0];
        const firstSentence = lines.slice(1)
            .find(line => line.includes('.'))
            ?.split('.')[0] + '.' || '';

        const imagePrompt = `$${title}: ${firstSentence}`;
        loadingDiv.textContent = 'Sending request to image generator...';

        const response = await fetch('/generate-image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: imagePrompt,
                username: user,
                index: index
            })
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        loadingDiv.textContent = 'Processing generated image...';
        const imageBlob = await response.blob();
        const imageUrl = URL.createObjectURL(imageBlob);

        // Create image element
        const imageElement = new Image();

        // Set up image load handling
        imageElement.onload = () => {
            imageElement.className = 'generated-image';
            imageElement.style = 'max-width: 100%; margin-top: 10px; opacity: 0;';
            imageContainer.appendChild(imageElement);

            // Fade in the image lol
            requestAnimationFrame(() => {
                imageElement.style.transition = 'opacity 0.5s ease-in';
                imageElement.style.opacity = '1';
                loadingDiv.remove();
            });
        };
        // Set the image source to trigger loading
        imageElement.src = imageUrl;
        imagesGenerated.push(index);
    } catch (error) {
        outputDiv.innerHTML += `<p style="color: red;" class="model-error">Error generating image: ${error}</p>`;
    } finally {
        generatingImage = false;
    }
}
