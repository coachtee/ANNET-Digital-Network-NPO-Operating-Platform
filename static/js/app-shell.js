// Bohlale Impact authenticated shell (organisation workspace + staff
// portal) -- sidebar collapse/expand and the mobile off-canvas drawer.
// Progressive enhancement only: without JS the sidebar just stays expanded
// and always visible, same as before this redesign.
(function () {
  var shell = document.querySelector(".app-shell");
  var sidebar = document.querySelector(".app-sidebar");
  if (!shell || !sidebar) return;

  var STORAGE_KEY = "bohlale-sidebar-collapsed";

  var collapseBtn = document.querySelector("[data-sidebar-toggle]");
  if (collapseBtn) {
    if (window.localStorage && window.localStorage.getItem(STORAGE_KEY) === "1") {
      sidebar.classList.add("collapsed");
    }
    collapseBtn.addEventListener("click", function () {
      var collapsed = sidebar.classList.toggle("collapsed");
      collapseBtn.setAttribute("aria-expanded", collapsed ? "false" : "true");
      if (window.localStorage) {
        window.localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
      }
    });
  }

  // Collapsed-rail tooltips are positioned in JS (not CSS ::after) because
  // the sidebar needs overflow-y:auto for long nav lists, and per the CSS
  // overflow spec that forces overflow-x to clip too -- a tooltip escaping
  // via left:100% inside that box would be cut off.
  var tooltip = null;
  function hideTooltip() {
    if (tooltip) {
      tooltip.remove();
      tooltip = null;
    }
  }
  sidebar.querySelectorAll(".sidebar-link").forEach(function (link) {
    link.addEventListener("mouseenter", function () {
      if (!sidebar.classList.contains("collapsed")) return;
      var label = link.getAttribute("data-label");
      if (!label) return;
      hideTooltip();
      tooltip = document.createElement("div");
      tooltip.className = "sidebar-tooltip" + (sidebar.classList.contains("staff-sidebar") ? " sidebar-tooltip--staff" : "");
      tooltip.textContent = label;
      document.body.appendChild(tooltip);
      var rect = link.getBoundingClientRect();
      tooltip.style.left = rect.right + 10 + "px";
      tooltip.style.top = rect.top + (rect.height - tooltip.offsetHeight) / 2 + "px";
    });
    link.addEventListener("mouseleave", hideTooltip);
  });

  var mobileToggle = document.querySelector("[data-mobile-nav-toggle]");
  var backdrop = document.querySelector("[data-mobile-nav-backdrop]");
  function closeMobileNav() {
    shell.classList.remove("mobile-nav-open");
    if (mobileToggle) mobileToggle.setAttribute("aria-expanded", "false");
  }
  if (mobileToggle) {
    mobileToggle.addEventListener("click", function () {
      var open = shell.classList.toggle("mobile-nav-open");
      mobileToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
  if (backdrop) {
    backdrop.addEventListener("click", closeMobileNav);
  }
  sidebar.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", closeMobileNav);
  });
})();
