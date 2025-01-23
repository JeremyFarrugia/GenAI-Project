
var audio = new Audio();


document.addEventListener("DOMContentLoaded", async function (event) {
    await userOnPageLoad();
});

function playAudio(data_path) {
    if (isAudioPlaying()) {
        console.log('Button disabled because audio is already playing');
        return;
    }

    // NOTE: data_path should be received in the form '<username>/stories/<story_id>'

    console.log("Data path: " + data_path);
    // Do something
}

function isAudioPlaying() {
    console.log('audio.paused: ' + audio.paused);
    return !audio.paused;
}