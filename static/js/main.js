document.addEventListener("DOMContentLoaded", function () {
    const alerts = document.querySelectorAll(".alert");
    if (!alerts.length) return;

    setTimeout(() => {
        alerts.forEach((alert) => {
            alert.style.transition = "opacity 0.4s ease";
            alert.style.opacity = "0";
            setTimeout(() => alert.remove(), 450);
        });
    }, 2200);
});