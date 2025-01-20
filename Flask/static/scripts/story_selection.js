var audio = new Audio();




// TODO - Organise into sub-scripts

document.addEventListener("DOMContentLoaded", async function (event) {
    await userOnPageLoad();
});



async function playAudio(parentDiv) {
    
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
