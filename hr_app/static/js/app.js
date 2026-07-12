document.addEventListener('DOMContentLoaded', function () {
    // Sidebar toggle
    const toggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
        });
    }

    // Notification dropdown
    const notifBtn = document.getElementById('notif-btn');
    const notifMenu = document.getElementById('notif-menu');
    if (notifBtn && notifMenu) {
        notifBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            notifMenu.classList.toggle('hidden');
        });
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.notif-dropdown')) {
                notifMenu.classList.add('hidden');
            }
        });
    }

    // Mark notification read
    document.querySelectorAll('.notif-item').forEach(item => {
        item.addEventListener('click', function () {
            const id = this.dataset.id;
            if (id) {
                fetch(`/auth/api/notifications/${id}/read`, { method: 'POST' });
            }
        });
    });

    // Mark all read
    const markAllBtn = document.getElementById('mark-all-read');
    if (markAllBtn) {
        markAllBtn.addEventListener('click', () => {
            fetch('/auth/api/notifications/read-all', { method: 'POST' }).then(() => {
                document.querySelectorAll('.notif-item').forEach(el => el.remove());
                const badge = document.querySelector('.notif-badge');
                if (badge) badge.remove();
            });
        });
    }

    // Auto-close flash messages
    document.querySelectorAll('.flash-success, .flash-danger, .flash-warning, .flash-info').forEach(el => {
        setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.5s'; }, 4000);
        setTimeout(() => { el.remove(); }, 4500);
    });
});
