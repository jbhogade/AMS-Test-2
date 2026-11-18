/* AMS-Test-2 app helpers: modals, toasts, user menu, password toggle */
(function () {
  "use strict";

  // ---- modals ----------------------------------------------------------
  window.openModal = function (id) {
    var d = document.getElementById(id);
    if (d && d.showModal) d.showModal();
  };
  window.closeModal = function (id) {
    var d = document.getElementById(id);
    if (d && d.open) d.close();
  };
  document.addEventListener("click", function (e) {
    var closer = e.target.closest("[data-close-modal]");
    if (closer) {
      var dlg = closer.closest("dialog");
      if (dlg) dlg.close();
    }
    var opener = e.target.closest("[data-open-modal]");
    if (opener) {
      e.preventDefault();
      var d = document.getElementById(opener.getAttribute("data-open-modal"));
      if (d) d.showModal();
    }
  });

  // ---- user chip menu ----------------------------------------------------
  var chip = document.querySelector(".user-chip");
  if (chip) {
    var btn = chip.querySelector("button");
    var menu = chip.querySelector(".user-menu");
    btn.addEventListener("click", function (e) { e.stopPropagation(); menu.classList.toggle("open"); });
    document.addEventListener("click", function () { menu.classList.remove("open"); });
  }

  // ---- toasts (Django messages + htmx OOB) --------------------------------
  window.toast = function (message, type) {
    var stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      document.body.appendChild(stack);
    }
    var t = document.createElement("div");
    t.className = "toast " + (type || "info");
    t.textContent = message;
    stack.appendChild(t);
    setTimeout(function () { t.style.opacity = "0"; t.style.transition = "opacity .3s"; }, 4200);
    setTimeout(function () { t.remove(); }, 4600);
  };
  document.querySelectorAll(".toast-stack .toast").forEach(function (t) {
    setTimeout(function () { t.style.opacity = "0"; t.style.transition = "opacity .3s"; }, 4200);
    setTimeout(function () { t.remove(); }, 4600);
  });

  // ---- password show/hide --------------------------------------------------
  document.addEventListener("click", function (e) {
    if (e.target.classList.contains("pw-toggle")) {
      var input = e.target.parentElement.querySelector("input");
      if (input) {
        input.type = input.type === "password" ? "text" : "password";
        e.target.textContent = input.type === "password" ? "Show" : "Hide";
      }
    }
  });

  // ---- confirm submits -------------------------------------------------------
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form.dataset.confirm) {
      if (!window.confirm(form.dataset.confirm)) { e.preventDefault(); }
    }
  });

  // ---- htmx: refresh toasts sent as OOB ----------------------------------------
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    var oob = evt.detail.xhr.getResponseHeader("HX-Tigger");
  });

  // auto-open a dialog when the URL has #modal-id
  if (location.hash && location.hash.indexOf("#m-") === 0) {
    var target = document.getElementById(location.hash.slice(1));
    if (target && target.showModal) target.showModal();
  }
})();
