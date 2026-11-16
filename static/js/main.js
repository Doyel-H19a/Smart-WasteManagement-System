(function () {
  "use strict";

  // 1. Bootstrap client-side validation for forms with .needs-validation
  document.querySelectorAll(".needs-validation").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    });
  });

  // 2. Password confirmation check (registration page)
  var p1 = document.getElementById("id_password1");
  var p2 = document.getElementById("id_password2");
  if (p1 && p2) {
    var checkMatch = function () {
      p2.setCustomValidity(p2.value && p1.value !== p2.value ? "Passwords do not match" : "");
    };
    p1.addEventListener("input", checkMatch);
    p2.addEventListener("input", checkMatch);
  }

  // 3. Mobile sidebar toggle
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.getElementById("sidebarBackdrop");
  var toggle = document.getElementById("sidebarToggle");
  var closeBtn = document.getElementById("sidebarClose");

  function setSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("show", open);
    if (backdrop) backdrop.classList.toggle("show", open);
    document.body.classList.toggle("overflow-hidden", open);
  }
  if (toggle) toggle.addEventListener("click", function () { setSidebar(true); });
  if (closeBtn) closeBtn.addEventListener("click", function () { setSidebar(false); });
  if (backdrop) backdrop.addEventListener("click", function () { setSidebar(false); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") setSidebar(false);
  });

  // 4. Auto-dismiss success/info alerts after 6 seconds
  document.querySelectorAll(".alert[data-auto-dismiss]").forEach(function (el) {
    setTimeout(function () {
      bootstrap.Alert.getOrCreateInstance(el).close();
    }, 6000);
  });
})();