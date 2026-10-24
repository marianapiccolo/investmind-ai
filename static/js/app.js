document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("sidebarToggle");

  const sidebar = document.getElementById("appSidebar");

  if (!toggle || !sidebar) {
    return;
  }

  toggle.addEventListener("click", () => {
    sidebar.classList.toggle("sidebar-open");
  });
});
