// =====================================================
// auth.js — Handles Login, Signup, OTP, Forgot Password
// Place this at: static/js/auth.js
// =====================================================

// ===== UTILITY =====
function showError(msg) {
    const el = document.getElementById('errorMsg');
    if (el) { el.textContent = msg; el.style.display = 'block'; }
}
function hideError() {
    const el = document.getElementById('errorMsg');
    if (el) el.style.display = 'none';
}
function showSuccess(msg) {
    const el = document.getElementById('successMsg');
    if (el) { el.textContent = msg; el.style.display = 'block'; }
}
function setLoading(btn, loading) {
    if (!btn) return;
    btn.disabled = loading;
    btn.textContent = loading ? 'Please wait...' : btn.dataset.originalText;
}

// ===== LOGIN =====
const loginForm = document.getElementById('loginForm');
if (loginForm) {
    const btn = loginForm.querySelector('button[type="submit"]');
    if (btn) btn.dataset.originalText = btn.textContent;

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();

        const email    = loginForm.email.value.trim();
        const password = loginForm.password.value;
        const btn      = loginForm.querySelector('button[type="submit"]');

        if (!email || !password) { showError('Please fill in all fields.'); return; }

        setLoading(btn, true);
        try {
            const res  = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();

            if (data.success) {
                // Store session token
                localStorage.setItem('session_token', data.session_token);
                localStorage.setItem('user_name',     data.user?.full_name || 'User');
                // Redirect to the main app
                window.location.href = '/dashboard';
            } else {
                showError(data.message || 'Login failed. Check your credentials.');
            }
        } catch (err) {
            showError('Network error. Is the server running?');
        } finally {
            setLoading(btn, false);
        }
    });
}

// ===== SIGNUP =====
const signupForm = document.getElementById('signupForm');
if (signupForm) {
    const btn = signupForm.querySelector('button[type="submit"]');
    if (btn) btn.dataset.originalText = btn.textContent;

    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();

        const full_name = signupForm.full_name.value.trim();
        const email     = signupForm.email.value.trim();
        const password  = signupForm.password.value;
        const btn       = signupForm.querySelector('button[type="submit"]');

        if (!full_name || !email || !password) { showError('Please fill in all fields.'); return; }
        if (password.length < 6) { showError('Password must be at least 6 characters.'); return; }

        setLoading(btn, true);
        try {
            const res  = await fetch('/api/auth/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ full_name, email, password })
            });
            const data = await res.json();

            if (data.success) {
                // Store email for OTP page
                localStorage.setItem('otp_email',    email);
                localStorage.setItem('otp_type',     'signup');
                localStorage.setItem('user_fullname', full_name);
                window.location.href = '/verify-otp';
            } else {
                showError(data.message || 'Signup failed. Try again.');
            }
        } catch (err) {
            showError('Network error. Is the server running?');
        } finally {
            setLoading(btn, false);
        }
    });
}

// ===== VERIFY OTP =====
const otpForm = document.getElementById('otpForm');
if (otpForm) {
    const btn = otpForm.querySelector('button[type="submit"]');
    if (btn) btn.dataset.originalText = btn.textContent;

    // Show email hint on the page
    const email    = localStorage.getItem('otp_email');
    const otpType  = localStorage.getItem('otp_type') || 'signup';
    const hint     = document.getElementById('emailHint');
    if (hint && email) hint.textContent = `Code sent to ${email}`;

    const newPasswordField = document.getElementById('newPasswordField');
    let otpVerified = false; // tracks whether OTP step is done

    otpForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();

        const btn = otpForm.querySelector('button[type="submit"]');

        if (!email) { showError('Session expired. Please start over.'); return; }

        // ── STEP 2: OTP already verified, now set new password ──
        if (otpType === 'password_reset' && otpVerified) {
            const new_password = (otpForm.querySelector('input[name="new_password"]')?.value || '').trim();
            if (new_password.length < 6) {
                showError('New password must be at least 6 characters.');
                return;
            }
            const otp = localStorage.getItem('verified_otp') || '';
            setLoading(btn, true);
            try {
                const res  = await fetch('/api/auth/reset-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, otp, new_password })
                });
                const data = await res.json();
                if (data.success) {
                    localStorage.removeItem('otp_email');
                    localStorage.removeItem('otp_type');
                    localStorage.removeItem('verified_otp');
                    showSuccess('Password reset! Redirecting to login...');
                    setTimeout(() => window.location.href = '/login', 1500);
                } else {
                    showError(data.message || 'Failed to reset password.');
                }
            } catch (err) {
                showError('Network error. Is the server running?');
            } finally {
                setLoading(btn, false);
            }
            return;
        }

        // ── STEP 1: Verify the OTP ──
        const otp = otpForm.otp.value.trim();
        if (otp.length !== 6) { showError('Enter the 6-digit code.'); return; }

        setLoading(btn, true);
        try {
            const res  = await fetch('/api/auth/verify-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email, otp,
                    type: otpType,
                    full_name: localStorage.getItem('user_fullname') || ''
                })
            });
            const data = await res.json();

            if (data.success) {
                if (otpType === 'password_reset') {
                    // OTP verified — now ask for new password
                    otpVerified = true;
                    localStorage.setItem('verified_otp', otp);
                    // Hide OTP input, show new password field
                    otpForm.querySelector('input[name="otp"]').style.display = 'none';
                    if (newPasswordField) {
                        newPasswordField.style.display = 'block';
                        newPasswordField.querySelector('input').required = true;
                        newPasswordField.querySelector('input').focus();
                    }
                    document.querySelector('.auth-card h1').textContent = 'Set New Password';
                    document.querySelector('.auth-subtitle').textContent = 'OTP verified! Enter your new password below.';
                    btn.textContent = 'Reset Password';
                    btn.dataset.originalText = 'Reset Password';
                } else {
                    // Signup — done
                    localStorage.removeItem('otp_email');
                    localStorage.removeItem('otp_type');
                    localStorage.removeItem('user_fullname');
                    showSuccess('Email verified! Redirecting to login...');
                    setTimeout(() => window.location.href = '/login', 1500);
                }
            } else {
                showError(data.message || 'Invalid OTP. Try again.');
            }
        } catch (err) {
            showError('Network error. Is the server running?');
        } finally {
            setLoading(btn, false);
        }
    });

    // Resend OTP
    const resendBtn = document.getElementById('resendOtp');
    if (resendBtn) {
        resendBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (!email) { showError('No email found. Please start over.'); return; }
            try {
                const endpoint = otpType === 'password_reset'
                    ? '/api/auth/forgot-password'
                    : '/api/auth/signup';
                await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email })
                });
                showSuccess('OTP resent! Check your inbox.');
            } catch (err) {
                showError('Failed to resend. Try again.');
            }
        });
    }
}

// ===== FORGOT PASSWORD =====
const forgotForm = document.getElementById('forgotForm');
if (forgotForm) {
    const btn = forgotForm.querySelector('button[type="submit"]');
    if (btn) btn.dataset.originalText = btn.textContent;

    forgotForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();

        const email = forgotForm.email.value.trim();
        const btn   = forgotForm.querySelector('button[type="submit"]');

        if (!email) { showError('Please enter your email.'); return; }

        setLoading(btn, true);
        try {
            const res  = await fetch('/api/auth/forgot-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            const data = await res.json();

            if (data.success) {
                localStorage.setItem('otp_email', email);
                localStorage.setItem('otp_type',  'password_reset');
                showSuccess('OTP sent! Check your email.');
                setTimeout(() => window.location.href = '/verify-otp', 1500);
            } else {
                showError(data.message || 'Failed. Try again.');
            }
        } catch (err) {
            showError('Network error. Is the server running?');
        } finally {
            setLoading(btn, false);
        }
    });
}

/*// =====================================================
// auth.js — Handles Login, Signup, OTP, Forgot Password
// Place this at: static/js/auth.js
// =====================================================

// ===== UTILITY =====
function showError(msg) {
    const el = document.getElementById('errorMsg');
    if (el) { el.textContent = msg; el.style.display = 'block'; }
}
function hideError() {
    const el = document.getElementById('errorMsg');
    if (el) el.style.display = 'none';
}
function showSuccess(msg) {
    const el = document.getElementById('successMsg');
    if (el) { el.textContent = msg; el.style.display = 'block'; }
}
function setLoading(btn, loading) {
    if (!btn) return;
    btn.disabled = loading;
    btn.textContent = loading ? 'Please wait...' : btn.dataset.originalText;
}

// ===== LOGIN =====
const loginForm = document.getElementById('loginForm');
if (loginForm) {
    const btn = loginForm.querySelector('button[type="submit"]');
    if (btn) btn.dataset.originalText = btn.textContent;

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();

        const email    = loginForm.email.value.trim();
        const password = loginForm.password.value;
        const btn      = loginForm.querySelector('button[type="submit"]');

        if (!email || !password) { showError('Please fill in all fields.'); return; }

        setLoading(btn, true);
        try {
            const res  = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();

            if (data.success) {
                // Store session token
                localStorage.setItem('session_token', data.session_token);
                localStorage.setItem('user_name',     data.user?.full_name || 'User');
                // Redirect to the main app
                window.location.href = '/dashboard';
            } else {
                showError(data.message || 'Login failed. Check your credentials.');
            }
        } catch (err) {
            showError('Network error. Is the server running?');
        } finally {
            setLoading(btn, false);
        }
    });
}

// ===== SIGNUP =====
const signupForm = document.getElementById('signupForm');
if (signupForm) {
    const btn = signupForm.querySelector('button[type="submit"]');
    if (btn) btn.dataset.originalText = btn.textContent;

    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();

        const full_name = signupForm.full_name.value.trim();
        const email     = signupForm.email.value.trim();
        const password  = signupForm.password.value;
        const btn       = signupForm.querySelector('button[type="submit"]');

        if (!full_name || !email || !password) { showError('Please fill in all fields.'); return; }
        if (password.length < 6) { showError('Password must be at least 6 characters.'); return; }

        setLoading(btn, true);
        try {
            const res  = await fetch('/api/auth/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ full_name, email, password })
            });
            const data = await res.json();

            if (data.success) {
                // Store email for OTP page
                localStorage.setItem('otp_email',    email);
                localStorage.setItem('otp_type',     'signup');
                localStorage.setItem('user_fullname', full_name);
                window.location.href = '/verify-otp';
            } else {
                showError(data.message || 'Signup failed. Try again.');
            }
        } catch (err) {
            showError('Network error. Is the server running?');
        } finally {
            setLoading(btn, false);
        }
    });
}

// ===== VERIFY OTP =====
const otpForm = document.getElementById('otpForm');
if (otpForm) {
    const btn = otpForm.querySelector('button[type="submit"]');
    if (btn) btn.dataset.originalText = btn.textContent;

    // Show email hint on the page
    const email    = localStorage.getItem('otp_email');
    const otpType  = localStorage.getItem('otp_type') || 'signup';
    const hint     = document.getElementById('emailHint');
    if (hint && email) hint.textContent = `Code sent to ${email}`;

    otpForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();

        const otp = otpForm.otp.value.trim();
        const btn = otpForm.querySelector('button[type="submit"]');

        if (!email)       { showError('Session expired. Please sign up again.'); return; }
        if (otp.length !== 6) { showError('Enter the 6-digit code.'); return; }

        setLoading(btn, true);
        try {
            const res  = await fetch('/api/auth/verify-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email,
                    otp,
                    type: otpType,
                    full_name: localStorage.getItem('user_fullname') || ''
                })
            });
            const data = await res.json();

            if (data.success) {
                localStorage.removeItem('otp_email');
                localStorage.removeItem('otp_type');
                localStorage.removeItem('user_fullname');

                if (otpType === 'signup') {
                    showSuccess('Email verified! Redirecting to login...');
                    setTimeout(() => window.location.href = '/login', 1500);
                } else if (otpType === 'password_reset') {
                    window.location.href = '/reset-password';
                }
            } else {
                showError(data.message || 'Invalid OTP. Try again.');
            }
        } catch (err) {
            showError('Network error. Is the server running?');
        } finally {
            setLoading(btn, false);
        }
    });

    // Resend OTP
    const resendBtn = document.getElementById('resendOtp');
    if (resendBtn) {
        resendBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (!email) { showError('No email found. Please start over.'); return; }
            try {
                const endpoint = otpType === 'password_reset'
                    ? '/api/auth/forgot-password'
                    : '/api/auth/signup';
                await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email })
                });
                showSuccess('OTP resent! Check your inbox.');
            } catch (err) {
                showError('Failed to resend. Try again.');
            }
        });
    }
}

// ===== FORGOT PASSWORD =====
const forgotForm = document.getElementById('forgotForm');
if (forgotForm) {
    const btn = forgotForm.querySelector('button[type="submit"]');
    if (btn) btn.dataset.originalText = btn.textContent;

    forgotForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();

        const email = forgotForm.email.value.trim();
        const btn   = forgotForm.querySelector('button[type="submit"]');

        if (!email) { showError('Please enter your email.'); return; }

        setLoading(btn, true);
        try {
            const res  = await fetch('/api/auth/forgot-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            const data = await res.json();

            if (data.success) {
                localStorage.setItem('otp_email', email);
                localStorage.setItem('otp_type',  'password_reset');
                showSuccess('OTP sent! Check your email.');
                setTimeout(() => window.location.href = '/verify-otp', 1500);
            } else {
                showError(data.message || 'Failed. Try again.');
            }
        } catch (err) {
            showError('Network error. Is the server running?');
        } finally {
            setLoading(btn, false);
        }
    });
} */