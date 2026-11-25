/* RouteRate - shared page behaviour (vanilla JavaScript, no framework). */
(function () {
  "use strict";

  // Mobile sidebar
  document.querySelectorAll("[data-sidebar-toggle]").forEach((btn) =>
    btn.addEventListener("click", () => document.body.classList.add("sidebar-open")));
  document.querySelectorAll("[data-sidebar-close]").forEach((el) =>
    el.addEventListener("click", () => document.body.classList.remove("sidebar-open")));

  // Forms with data-confirm ask before submitting (delete, discard...)
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  // Buttons that submit long operations show a spinner and cannot be double-clicked
  document.querySelectorAll("form[data-busy]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (event.defaultPrevented) return;
      const btn = form.querySelector("button[type=submit]:not([data-no-busy])");
      if (!btn) return;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>' +
        (form.dataset.busy || "Working…");
    });
  });

  // Auto-submit filter selects (class="auto-submit")
  document.querySelectorAll("select.auto-submit, input.auto-submit").forEach((el) =>
    el.addEventListener("change", () => el.form && el.form.submit()));

  // Bootstrap tooltips
  if (window.bootstrap) {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => new bootstrap.Tooltip(el));
  }

  // Auto-hide success messages
  document.querySelectorAll(".alert-success").forEach((el) => {
    setTimeout(() => window.bootstrap && bootstrap.Alert.getOrCreateInstance(el).close(), 6000);
  });
})();
