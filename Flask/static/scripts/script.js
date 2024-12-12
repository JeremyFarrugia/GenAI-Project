var outputDiv;
var promptInput;
var promptHistory = [];
var promptHistoryIndex = 0;
const user = 'Guest'; // The user's name (temporary)

document.addEventListener("DOMContentLoaded", async function (event) {
    outputDiv = document.getElementById('output');
    promptInput = document.getElementById('prompt-input');

    promptInput.addEventListener
    // Execute the prompt when the user presses Enter
    promptInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') executePrompt();
    });

    promptInput.addEventListener('keydown', (e) => {
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
    });

    // Focus on the input field
    promptInput.focus();
});


async function executePrompt() {
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
    outputDiv.innerHTML += `<p style="color: #00ff00;" class = user-prompt>${user}> ${prompt}</p>`;

    try {
        const response = await fetch('/prompt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prompt })
        });

        const result = await response.json();

        if (result.success) {
            if (result.reply) {
                outputDiv.innerHTML += `<p class=model-response>david> ${result.reply}</p>`;
            }
        } else {
            outputDiv.innerHTML += `<p style="color: red;" class = model-error>Error: ${result.error}</p>`;
        }
    } catch (error) {
        outputDiv.innerHTML += `<p style="color: red;" class = model-error>Error: ${error}</p>`;
    }

    // Scroll to the bottom and clear the input
    outputDiv.scrollTop = outputDiv.scrollHeight;
    promptInput.value = '';
}