
var audio = new Audio();
var listening = false;
var currentIndex = 1;
var soundEffectNext = false;
var global_data_path = '';
var inTimeout = true;
var music = new Audio();

const textColour = "#ececec";
const highlightColour = "#f0f0f0";
const highlightBackgroundColour = "#000000";

function getStoryID(){
    const story_content = document.getElementById("story-content");
    return story_content.getAttribute("story_id");
}

function highlightNextParagraph(){
    const storyTexts = document.getElementsByClassName('story-text');
    if(currentIndex > storyTexts.length){
        return;
    }
    
    highlightIndex = currentIndex - 1;
    if(highlightIndex > 0){ // Unhighlight the previous paragraph
        storyTexts[highlightIndex - 1].style.color = textColour;
        // Reset background colour
        storyTexts[highlightIndex - 1].style.backgroundColor = "transparent";
    }
    storyTexts[highlightIndex].style.color = highlightColour;
    storyTexts[highlightIndex].style.backgroundColor = highlightBackgroundColour;
}

document.addEventListener("DOMContentLoaded", async function (event) {
    await userOnPageLoad();
});

async function togglePublic(isPublic){

    try {
        const response = await fetch('/toggle-public', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                isPublic: isPublic,
                storyID: getStoryID()
            })
        });

        if(!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        // Refresh if successful
        location.reload();
    }
    catch (error) {
        console.error('Error:', error);
    }
}

async function regenerateStory(){
    try {
        const response = await fetch('/regenerate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                storyID: getStoryID()
            })
        });

        if(!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        // Refresh if successful
        location.reload();
    }
    catch (error) {
        console.error('Error:', error);
    }
}

function playAudio(data_path) {
    if (isAudioPlaying()) {
        console.log('Button disabled because audio is already playing');
        return;
    }

    
    // NOTE: data_path should be received in the form '<username>/stories/<story_id>'

    global_data_path = data_path;

    console.log("Data path: " + data_path);
    // Do something

    listening = true;
    transitionToNextAudio();
    requestMusic();
    window.requestAnimationFrame(loop); // Start the loop
}

function getMaxIndex() {
    // Get max index by counting the number of paragraphs
    // Count amount of dom elements with class 'story-text'
    const storyTexts = document.getElementsByClassName('story-text');
    return storyTexts.length;
}

function isAudioPlaying() {
    console.log('audio.paused: ' + audio.paused);
    return !audio.paused;
}

async function transitionToNextAudio() {
    console.log('Transitioning to next audio, currentIndex: ' + currentIndex);
    if (currentIndex > getMaxIndex()) {
        console.log('End of story');
        // End of story
        listening = false;
        music.pause();
        return;
    }

    nextAudio = ''
    if (soundEffectNext) {
        nextAudio = `audio_${currentIndex}`;
        soundEffectNext = false;
        currentIndex++;
    }
    else {
        nextAudio = `paragraph_${currentIndex}`;
        highlightNextParagraph();
        soundEffectNext = true;
    }

    console.log('Transitioning to ' + nextAudio);

    // Set a delay before playing next audio
    inTimeout = true;
    await new Promise(r => setTimeout(r, 100));
    await requestAudio(nextAudio);
    inTimeout = false;
}

async function requestAudio(nextAudio) {
    

    try {
        const response = await fetch('/get-audio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                data_path: global_data_path,
                file: nextAudio
            })
        });

        if(!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        audio = new Audio(audioUrl);
        audio.play();
    }
    catch (error) {
        console.error('Error:', error);
    }
}

async function requestMusic() {
    try {
        const response = await fetch('/get-audio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                data_path: global_data_path,
                file: 'music'
            })
        });

        if(!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        music = new Audio(audioUrl);
        // Lower the volume
        music.volume = 0.1;
        music.loop = true;
        music.play();
    }
    catch (error) {
        console.error('Error:', error);
    }
}

// Something experimental based on a previous project

async function loop() {
    if (listening) {
        if(!isAudioPlaying() && !inTimeout) {
            transitionToNextAudio();
        }
    }
    else {
        // End loop
        return;
    }

    window.requestAnimationFrame(loop); // request the next frame
}