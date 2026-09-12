document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("menu-toggle");
  const overlay = document.getElementById("sidebar-overlay");

  if (!toggle) return; // لا توجد قائمة في صفحات الضيف (تسجيل الدخول)

  function closeNav() { document.body.classList.remove("nav-open"); }
  function openNav() { document.body.classList.add("nav-open"); }

  toggle.addEventListener("click", () => {
    document.body.classList.contains("nav-open") ? closeNav() : openNav();
  });

  overlay.addEventListener("click", closeNav);

  // إغلاق القائمة تلقائياً عند الضغط على أي رابط تنقل (تجربة جوال أفضل)
  document.querySelectorAll(".sidebar nav a").forEach(link => {
    link.addEventListener("click", closeNav);
  });
});
