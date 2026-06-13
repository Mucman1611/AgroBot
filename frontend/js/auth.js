
const API_URL = 'http://localhost:5000/api';

function showLoginModal() { document.getElementById('loginModal').classList.add('active'); }
function closeLoginModal() { document.getElementById('loginModal').classList.remove('active'); }
function showRegisterModal() { document.getElementById('registerModal').classList.add('active'); }
function closeRegisterModal() { document.getElementById('registerModal').classList.remove('active'); }

document.getElementById('loginBtnNav').onclick = (e) => { e.preventDefault(); showLoginModal(); };
document.getElementById('registerBtnNav').onclick = (e) => { e.preventDefault(); showRegisterModal(); };
document.getElementById('registerBtnHero').onclick = (e) => { e.preventDefault(); showRegisterModal(); };
document.getElementById('agentBtnHero').onclick = (e) => {
    e.preventDefault();
    document.getElementById('regRole').value = 'agent';
    showRegisterModal();
};

document.getElementById('regRole').onchange = function () {
    document.getElementById('delegatedToGroup').style.display = this.value === 'grandchild' ? 'block' : 'none';
};

document.getElementById('loginForm').onsubmit = async (e) => {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    try {
        const response = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();
        if (response.ok) {
            localStorage.setItem('token', data.token);
            localStorage.setItem('userRole', data.role);
            localStorage.setItem('userId', data.user_id);
            localStorage.setItem('userName', data.full_name);
            window.location.href = data.role === 'agent' ? 'agent-dashboard.html' : 'farmer-dashboard.html';
        } else {
            document.getElementById('loginAlert').innerHTML = `<div class="alert alert-error">${data.detail || data.error}</div>`;
        }
    } catch {
        document.getElementById('loginAlert').innerHTML = `<div class="alert alert-error">Greška pri povezivanju s poslužiteljem</div>`;
    }
};

document.getElementById('registerForm').onsubmit = async (e) => {
    e.preventDefault();
    const role = document.getElementById('regRole').value;
    const delegatedToEmail = document.getElementById('delegatedToEmail').value;
    const body = {
        full_name: document.getElementById('regName').value,
        email: document.getElementById('regEmail').value,
        password: document.getElementById('regPassword').value,
        role
    };
    if (role === 'grandchild' && delegatedToEmail) {
        const userRes = await fetch(`${API_URL}/user/by-email?email=${delegatedToEmail}`);
        const userData = await userRes.json();
        if (userData.id) body.delegated_to_id = userData.id;
    }
    try {
        const response = await fetch(`${API_URL}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();
        if (response.ok) {
            closeRegisterModal();
            showLoginModal();
            document.getElementById('loginAlert').innerHTML = '<div class="alert alert-success">Registracija uspješna! Prijavite se.</div>';
        } else {
            document.getElementById('registerAlert').innerHTML = `<div class="alert alert-error">${data.detail || data.error}</div>`;
        }
    } catch {
        document.getElementById('registerAlert').innerHTML = `<div class="alert alert-error">Greška pri registraciji</div>`;
    }
};