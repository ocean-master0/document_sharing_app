document.addEventListener('DOMContentLoaded', () => {
    const hour = new Date().getHours();
    const isNight = hour < 6 || hour >= 18;
    if (isNight) {
        document.body.classList.add('dark-mode');
    }

    const useCustomId = document.getElementById('useCustomId');
    const customUserId = document.getElementById('customUserId');
    if (useCustomId && customUserId) {
        useCustomId.addEventListener('change', () => {
            customUserId.disabled = !useCustomId.checked;
            if (!useCustomId.checked) customUserId.value = '';
        });
    }

    document.getElementById('downloadForm')?.addEventListener('submit', (e) => {
        e.preventDefault();

        const codeInput = document.querySelector('input[name="code"]');
        const code = codeInput ? codeInput.value.trim() : '';
        if (!code) return;

        const submitBtn = document.querySelector('#downloadForm button[type="submit"]');
        const originalText = submitBtn ? submitBtn.innerHTML : '';
        if (submitBtn) {
            submitBtn.innerHTML = '<span class="loader"></span> Verifying...';
            submitBtn.disabled = true;
        }

        const message = document.getElementById('message');
        const downloadInfo = document.getElementById('downloadInfo');

        fetch('/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `code=${encodeURIComponent(code)}`
        })
            .then(response => {
                if (!response.ok) return response.json().then(d => { throw new Error(d.error); });
                return response.json();
            })
            .then(data => {
                if (submitBtn) {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
                if (data.error) {
                    if (message) { message.textContent = data.error; message.className = 'error'; }
                    if (downloadInfo) downloadInfo.style.display = 'none';
                } else {
                    if (message) { message.textContent = 'Code is valid!'; message.className = 'success'; }
                    const userName = document.getElementById('userName');
                    const docName = document.getElementById('docName');
                    const downloadLink = document.getElementById('downloadLink');
                    if (userName) userName.textContent = data.user_name;
                    if (docName) docName.textContent = data.doc_name;
                    if (downloadLink) downloadLink.href = data.url;
                    if (downloadInfo) { downloadInfo.style.display = 'block'; downloadInfo.classList.add('fade-in'); }
                }
            })
            .catch((err) => {
                if (submitBtn) {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
                if (message) { message.textContent = err.message || 'An error occurred.'; message.className = 'error'; }
                if (downloadInfo) downloadInfo.style.display = 'none';
            });
    });

    const copyButtons = document.querySelectorAll('.copy-btn, .code-card-copy');
    copyButtons.forEach(button => {
        button.addEventListener('click', () => {
            const code = button.getAttribute('data-code');
            if (!code) return;
            navigator.clipboard.writeText(code).then(() => {
                const originalHTML = button.innerHTML;
                button.innerHTML = '<i class="bi bi-check-lg"></i>';
                button.classList.add('copied');
                setTimeout(() => {
                    button.innerHTML = originalHTML;
                    button.classList.remove('copied');
                }, 2000);
            }).catch(() => {
                const originalHTML = button.innerHTML;
                button.innerHTML = '<i class="bi bi-x-lg"></i>';
                setTimeout(() => {
                    button.innerHTML = originalHTML;
                }, 1500);
            });
        });
    });

    document.querySelectorAll('.require-pass').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const form = btn.closest('form');
            const passInput = form.querySelector('.pass-input');
            const promptMsg = btn.getAttribute('data-prompt') || 'Enter your password:';
            const password = prompt(promptMsg);
            if (!password) {
                e.preventDefault();
                return;
            }
            passInput.value = password;
        });
    });
});
