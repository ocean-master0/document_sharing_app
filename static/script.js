document.addEventListener('DOMContentLoaded', () => {
    
    // Dark Mode Toggle with System Preference Detection
    const darkModeToggle = document.getElementById('darkModeToggle');
    const body = document.body;
    
    // Check for system preference
    const prefersDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    // Initialize dark mode
    function initDarkMode() {
        const savedMode = localStorage.getItem('darkMode');
        const shouldUseDark = savedMode === 'enabled' || (savedMode === null && prefersDarkMode);
        
        if (shouldUseDark) {
            body.setAttribute('data-theme', 'dark');
            if (darkModeToggle) darkModeToggle.checked = true;
        } else {
            body.setAttribute('data-theme', 'light');
            if (darkModeToggle) darkModeToggle.checked = false;
        }
    }
    
    // Toggle dark mode
    if (darkModeToggle) {
        darkModeToggle.addEventListener('change', () => {
            if (darkModeToggle.checked) {
                body.setAttribute('data-theme', 'dark');
                localStorage.setItem('darkMode', 'enabled');
            } else {
                body.setAttribute('data-theme', 'light');
                localStorage.setItem('darkMode', 'disabled');
            }
        });
    }
    
    // Initialize on page load
    initDarkMode();
    
    // Listen for system theme changes
    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (localStorage.getItem('darkMode') === null) {
                if (e.matches) {
                    body.setAttribute('data-theme', 'dark');
                    if (darkModeToggle) darkModeToggle.checked = true;
                } else {
                    body.setAttribute('data-theme', 'light');
                    if (darkModeToggle) darkModeToggle.checked = false;
                }
            }
        });
    }
    
    // Custom User ID Toggle
    const useCustomId = document.getElementById('useCustomId');
    const customUserId = document.getElementById('customUserId');
    if (useCustomId && customUserId) {
        useCustomId.addEventListener('change', () => {
            customUserId.disabled = !useCustomId.checked;
            if (!useCustomId.checked) customUserId.value = '';
            
            // Add smooth transition effect
            customUserId.style.transition = 'opacity 0.3s ease';
            customUserId.style.opacity = useCustomId.checked ? '1' : '0.5';
        });
    }
    
    // Enhanced Download Form Handler
    const downloadForm = document.getElementById('downloadForm');
    if (downloadForm) {
        downloadForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const codeInput = document.querySelector('input[name="code"]');
            const code = codeInput.value.trim();
            
            if (!code) {
                showMessage('Please enter a download code', 'error');
                return;
            }
            
            // Add loading state with better UX
            const submitBtn = downloadForm.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<span style="display: inline-flex; align-items: center; gap: 8px;"><span class="spinner"></span>Verifying...</span>';
            submitBtn.disabled = true;
            
            // Add spinner styles
            if (!document.querySelector('.spinner-styles')) {
                const style = document.createElement('style');
                style.className = 'spinner-styles';
                style.textContent = `
                    .spinner {
                        width: 16px;
                        height: 16px;
                        border: 2px solid rgba(255,255,255,0.3);
                        border-top: 2px solid white;
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                    }
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                `;
                document.head.appendChild(style);
            }
            
            fetch('/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `code=${encodeURIComponent(code)}`
            })
            .then(response => response.json())
            .then(data => {
                const downloadInfo = document.getElementById('downloadInfo');
                const downloadLink = document.getElementById('downloadLink');
                const docName = document.getElementById('docName');
                
                // Reset button
                submitBtn.innerHTML = originalBtnText;
                submitBtn.disabled = false;
                
                if (data.error) {
                    showMessage(data.error, 'error');
                    if (downloadInfo) downloadInfo.style.display = 'none';
                } else {
                    showMessage('Code verified successfully! 🎉', 'success');
                    
                    // Update download information
                    if (docName) docName.textContent = data.doc_name;
                    if (downloadLink) downloadLink.href = data.url;
                    
                    // Show download info with animation
                    if (downloadInfo) {
                        downloadInfo.style.display = 'block';
                        downloadInfo.style.opacity = '0';
                        downloadInfo.style.transform = 'translateY(20px)';
                        
                        setTimeout(() => {
                            downloadInfo.style.transition = 'all 0.5s ease';
                            downloadInfo.style.opacity = '1';
                            downloadInfo.style.transform = 'translateY(0)';
                        }, 100);
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Network error. Please try again.', 'error');
                submitBtn.innerHTML = originalBtnText;
                submitBtn.disabled = false;
            });
        });
    }
    
    // Enhanced Copy to Clipboard
    const codeCopyButtons = document.querySelectorAll('.copy-btn');
    codeCopyButtons.forEach(button => {
        button.addEventListener('click', async () => {
            const code = button.getAttribute('data-code');
            
            try {
                await navigator.clipboard.writeText(code);
                
                // Visual feedback
                const originalHTML = button.innerHTML;
                button.innerHTML = '✅';
                button.classList.add('copied');
                
                // Show toast notification
                showToast(`Code ${code} copied to clipboard!`, 'success');
                
                setTimeout(() => {
                    button.innerHTML = originalHTML;
                    button.classList.remove('copied');
                }, 2000);
            } catch (err) {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = code;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                
                showToast(`Code ${code} copied to clipboard!`, 'success');
            }
        });
    });
    
    // Enhanced Message System
    function showMessage(message, type = 'info') {
        const messageContainer = document.getElementById('message');
        if (!messageContainer) return;
        
        messageContainer.textContent = message;
        messageContainer.className = type;
        
        // Add animation
        messageContainer.style.opacity = '0';
        messageContainer.style.transform = 'translateY(-10px)';
        messageContainer.style.transition = 'all 0.3s ease';
        
        setTimeout(() => {
            messageContainer.style.opacity = '1';
            messageContainer.style.transform = 'translateY(0)';
        }, 50);
    }
    
    // Toast Notification System
    function showToast(message, type = 'info') {
        // Remove existing toast
        const existingToast = document.querySelector('.toast');
        if (existingToast) existingToast.remove();
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        
        // Add toast styles
        if (!document.querySelector('.toast-styles')) {
            const style = document.createElement('style');
            style.className = 'toast-styles';
            style.textContent = `
                .toast {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 12px 20px;
                    border-radius: 8px;
                    color: white;
                    font-weight: 600;
                    font-size: 14px;
                    z-index: 1000;
                    opacity: 0;
                    transform: translateX(100%);
                    transition: all 0.3s ease;
                    max-width: 300px;
                }
                .toast-success { background: #38a169; }
                .toast-error { background: #e53e3e; }
                .toast-info { background: #3182ce; }
                .toast.show {
                    opacity: 1;
                    transform: translateX(0);
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Hide toast after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    // Form Validation Enhancement
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input[required]');
        
        inputs.forEach(input => {
            input.addEventListener('blur', () => {
                if (input.value.trim() === '') {
                    input.style.borderColor = 'var(--error)';
                    input.style.boxShadow = '0 0 0 3px rgba(229, 62, 62, 0.1)';
                } else {
                    input.style.borderColor = 'var(--success)';
                    input.style.boxShadow = '0 0 0 3px rgba(56, 161, 105, 0.1)';
                }
            });
            
            input.addEventListener('focus', () => {
                input.style.borderColor = 'var(--brand-primary)';
                input.style.boxShadow = '0 0 0 3px rgba(49, 130, 206, 0.1)';
            });
        });
    });
    
    // Smooth Scroll for Navigation
    const navLinks = document.querySelectorAll('.nav-item');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            // Add active state
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
        });
    });
    
    // Auto-save form data
    const formInputs = document.querySelectorAll('input[type="text"], input[type="email"], textarea');
    formInputs.forEach(input => {
        const storageKey = `form_${input.name || input.id}`;
        
        // Load saved data
        const savedValue = localStorage.getItem(storageKey);
        if (savedValue && !input.value) {
            input.value = savedValue;
        }
        
        // Save on change
        input.addEventListener('input', () => {
            localStorage.setItem(storageKey, input.value);
        });
    });
    
    // Clear saved form data on successful submission
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', () => {
            const inputs = form.querySelectorAll('input[type="text"], input[type="email"], textarea');
            inputs.forEach(input => {
                const storageKey = `form_${input.name || input.id}`;
                localStorage.removeItem(storageKey);
            });
        });
    });
    
});
