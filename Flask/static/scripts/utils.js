// General utility functions used throughout the application
const utils = {
    // Function to display modal with message for error handling
    displayModal: function (message) {
        const modal = document.getElementById('modalPopup');
        const modalMessage = document.getElementById('modal-message');
        modalMessage.textContent = message;
        modal.style.display = "block";

        // Close modal when user clicks on close button
        const closeBtn = document.getElementsByClassName("close")[0];
        closeBtn.onclick = function () {
            modal.style.display = "none";
        }
    },
}