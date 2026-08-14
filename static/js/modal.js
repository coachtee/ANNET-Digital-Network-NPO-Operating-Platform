// Reusable modal/drawer controller for Bohlale Impact workspaces.
// Progressive enhancement over plain server-rendered forms: every modal
// is always present in the DOM (closed by default), so a failed POST can
// force one open server-side via data-open-on-load, with Django's normal
// bound-form rendering already preserving entered values and errors --
// no fetch/AJAX layer needed.
(function () {
  function openModal(modal) {
    modal.classList.add("is-open");
    var firstField = modal.querySelector("input:not([type=hidden]), select, textarea");
    if (firstField) firstField.focus();
  }

  function closeModal(modal) {
    modal.classList.remove("is-open");
  }

  document.addEventListener("click", function (e) {
    var opener = e.target.closest("[data-modal-open]");
    if (opener) {
      var modal = document.getElementById(opener.getAttribute("data-modal-open"));
      if (modal) openModal(modal);
      return;
    }
    var closer = e.target.closest("[data-modal-close]");
    if (closer) {
      var toClose = closer.closest(".modal-backdrop");
      if (toClose) closeModal(toClose);
      return;
    }
    // Backdrop click (not a click inside .modal itself) closes.
    if (e.target.classList.contains("modal-backdrop")) {
      closeModal(e.target);
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    document.querySelectorAll(".modal-backdrop.is-open").forEach(closeModal);
  });

  document.querySelectorAll(".modal-backdrop[data-open-on-load='true']").forEach(openModal);
})();
