var user = 'User'; // The user's name (temporary)
var loggedIn = false; // Whether the user is logged in or not

var loginModal;
var loginButton;
var registerButton;

var registerModal;
var registerButton;

var accountModal;

async function userOnPageLoad() {
    loginModal = document.getElementById('loginModal');
    registerModal = document.getElementById('registerModal');
    accountModal = document.getElementById('accountModal');

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
}

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

        // Refresh the page to update the UI - lazy way of fixing UI issues that persist and clearing the chat
        location.reload();
    }


    swapLoginButton();
}

async function checkSession() {
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