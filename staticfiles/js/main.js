document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.alert-msg').forEach(function(el) {
        setTimeout(function() {
            el.style.transition = 'opacity 0.5s';
            el.style.opacity = '0';
            setTimeout(function() { el.remove(); }, 500);
        }, 3500);
    });
    var menuBtn  = document.getElementById('menu-btn');
    var overlay  = document.getElementById('sidebar-overlay');
    var mobileSb = document.getElementById('mobile-sidebar');
    if (menuBtn && mobileSb) {
        menuBtn.addEventListener('click', function() {
            mobileSb.classList.toggle('-translate-x-full');
            if (overlay) overlay.classList.toggle('hidden');
        });
    }
    if (overlay) {
        overlay.addEventListener('click', function() {
            if (mobileSb) mobileSb.classList.add('-translate-x-full');
            overlay.classList.add('hidden');
        });
    }
});
