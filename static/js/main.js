// Main JavaScript functionality for LivestreamTrap

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // Confirm destructive actions
    const destructiveButtons = document.querySelectorAll('button[class*="btn-danger"]');
    destructiveButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Вы уверены, что хотите выполнить это действие?')) {
                e.preventDefault();
            }
        });
    });

    // Live count auto-update
    function updateLiveCounts() {
        fetch('/api/live-counts/')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                document.querySelectorAll('.live-count').forEach(cell => {
                    const channelId = cell.getAttribute('data-channel-id');
                    if (data[channelId] !== undefined) {
                        cell.textContent = data[channelId];
                    }
                });
            })
            .catch(error => {
                console.error('Error updating live counts:', error);
            });
    }

    // Update live counts every minute if on home page
    if (document.querySelector('.live-count')) {
        setInterval(updateLiveCounts, 60000);
    }
});

// Utility function to format file sizes
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Form validation
function validateHandle(handle) {
    if (handle.length < 3 || handle.length > 30) {
        return 'Псевдоним должен содержать от 3 до 30 символов';
    }
    if (!/^[a-zA-Z0-9_-]+$/.test(handle)) {
        return 'Псевдоним может содержать только буквы, цифры, дефисы и подчёркивания';
    }
    return null;
}