document.addEventListener('DOMContentLoaded', () => {
    // Dark Mode Toggle
    const darkModeToggle = document.getElementById('darkModeToggle');
    
    if (localStorage.getItem('darkMode') === 'enabled') {
      document.body.classList.add('dark-mode');
      darkModeToggle.checked = true;
    }
    
    darkModeToggle.addEventListener('change', () => {
      document.body.classList.toggle('dark-mode');
      localStorage.setItem('darkMode', document.body.classList.contains('dark-mode') ? 'enabled' : 'disabled');
    });
    
    // Custom User ID Toggle
    const useCustomId = document.getElementById('useCustomId');
    const customUserId = document.getElementById('customUserId');
    
    if (useCustomId && customUserId) {
      useCustomId.addEventListener('change', () => {
        customUserId.disabled = !useCustomId.checked;
        if (!useCustomId.checked) customUserId.value = '';
      });
    }
    
    // Download Form Handler
    document.getElementById('downloadForm')?.addEventListener('submit', (e) => {
      e.preventDefault();
      
      const codeInput = document.querySelector('input[name="code"]');
      const code = codeInput.value;
      
      // Add loading state
      const submitBtn = document.querySelector('#downloadForm button[type="submit"]');
      const originalBtnText = submitBtn.innerHTML;
      submitBtn.innerHTML = '<span class="loader"></span> Verifying...';
      submitBtn.disabled = true;
      
      fetch('/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `code=${code}`
      })
        .then(response => response.json())
        .then(data => {
          const message = document.getElementById('message');
          const downloadInfo = document.getElementById('downloadInfo');
          const downloadLink = document.getElementById('downloadLink');
          const userName = document.getElementById('userName');
          const userId = document.getElementById('userId');
          const docName = document.getElementById('docName');
          
          // Reset button
          submitBtn.innerHTML = originalBtnText;
          submitBtn.disabled = false;
          
          if (data.error) {
            message.textContent = data.error;
            message.className = 'error';
            downloadInfo.style.display = 'none';
          } else {
            message.textContent = 'Code is valid!';
            message.className = 'success';
            userName.textContent = data.user_name;
            userId.textContent = data.user_id;
            docName.textContent = data.doc_name;
            downloadLink.href = data.url;
            downloadInfo.style.display = 'block';
            
            // Add fade-in effect
            downloadInfo.classList.add('fade-in');
          }
        })
        .catch(() => {
          message.textContent = 'An error occurred.';
          message.className = 'error';
          submitBtn.innerHTML = originalBtnText;
          submitBtn.disabled = false;
        });
    });
    
    // Copy code to clipboard functionality
    const codeCopyButtons = document.querySelectorAll('.copy-btn');
    codeCopyButtons.forEach(button => {
      button.addEventListener('click', () => {
        const code = button.getAttribute('data-code');
        navigator.clipboard.writeText(code).then(() => {
          const originalText = button.innerHTML;
          button.innerHTML = '<i class="fas fa-check"></i>';
          button.classList.add('copied');
          setTimeout(() => {
            button.innerHTML = originalText;
            button.classList.remove('copied');
          }, 2000);
        });
      });
    });
  });
  