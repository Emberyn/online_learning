// main.js
document.addEventListener('DOMContentLoaded', function() {
    // 为主要内容区域添加淡入动画
    const container = document.querySelector('.container.mt-4');
    if (container) {
        container.classList.add('fade-in');
    }

    // 自动隐藏提示信息 (Flash messages) - 5秒后
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            // 使用 Bootstrap 的 Alert API 关闭警告框
            if (typeof bootstrap !== 'undefined') {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } else {
                alert.style.display = 'none';
            }
        }, 5000);
    });

    // 为卡片内的链接添加点击效果反馈
    const cardLinks = document.querySelectorAll('.card .btn');
    cardLinks.forEach(btn => {
        btn.addEventListener('click', function(e) {
            let x = e.clientX - e.target.getBoundingClientRect().left;
            let y = e.clientY - e.target.getBoundingClientRect().top;
            
            let ripples = document.createElement('span');
            ripples.style.left = x + 'px';
            ripples.style.top = y + 'px';
            this.appendChild(ripples);
            
            setTimeout(() => {
                ripples.remove()
            }, 1000);
        });
    });
});