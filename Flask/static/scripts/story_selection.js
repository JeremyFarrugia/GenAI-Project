
document.addEventListener("DOMContentLoaded", async function (event) {
    await userOnPageLoad();
    setupStorySelection();
    
});

function setupStorySelection() {
    document.querySelectorAll(".story-preview").forEach(story => {
        story.addEventListener("click", function () {
            const url = this.getAttribute("target_url");
            if (url) {
                console.log("Redirecting to:", url);
                window.location.href = url;
            } else {
                console.error("No URL found!");
            }
        });
    });
}

function redirectToStory(url) {
    console.long('Redirecting to ' + url);
}

async function playAudio(parentDiv) {
    
}

