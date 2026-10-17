document.addEventListener("DOMContentLoaded", function () {
  const $ = (id) => document.getElementById(id);

  /* ---------- CAROUSEL (autoplay, swipe, dots) ---------- */
  const slidesEl = $("slides");
  if (slidesEl) {
    const slides = slidesEl.children;
    const dotsEl = $("dots");
    let index = 0, timer;

    for (let i = 0; i < slides.length; i++) dotsEl.appendChild(document.createElement("i"));
    const dots = dotsEl.children;

    function paintDots() {
      for (let i = 0; i < dots.length; i++) dots[i].classList.toggle("on", i === index);
    }
    function goTo(i) {
      index = (i + slides.length) % slides.length;
      slidesEl.scrollTo({ left: slides[index].offsetLeft - slidesEl.offsetLeft, behavior: "smooth" });
      paintDots();
    }
    function start() {
      stop();
      if (slides.length > 1) timer = setInterval(() => goTo(index + 1), 4000);
    }
    function stop() { clearInterval(timer); }

    slidesEl.addEventListener("scroll", function () {
      const i = Math.round(slidesEl.scrollLeft / slidesEl.clientWidth);
      if (i !== index && i >= 0 && i < slides.length) { index = i; paintDots(); }
    }, { passive: true });
    slidesEl.addEventListener("touchstart", stop, { passive: true });
    slidesEl.addEventListener("touchend", start, { passive: true });
    document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));

    paintDots();
    start();
  }

  /* ---------- SEARCH ---------- */
  const input = $("menuSearch");
  const clearBtn = $("clearSearch");
  const resultText = $("searchResultText");
  const emptyBox = $("searchEmpty");
  const cards = document.querySelectorAll(".food-card");
  const sections = document.querySelectorAll(".category");
  const extras = [document.querySelector(".carousel"), document.querySelector(".block-title"), $("catRow")];

  function searchMenu() {
    const q = input.value.trim().toLowerCase();
    let found = 0;

    cards.forEach(function (card) {
      const text = card.dataset.name + " " + card.dataset.description + " " + card.dataset.category;
      const match = q === "" || text.includes(q);
      card.style.display = match ? "" : "none";
      if (match) found++;
    });

    sections.forEach(function (sec) {
      const visible = sec.querySelectorAll('.food-card:not([style*="none"])').length;
      sec.style.display = q !== "" && visible === 0 ? "none" : "";
    });

    extras.forEach((el) => el && (el.style.display = q ? "none" : ""));

    clearBtn.style.display = q ? "flex" : "none";
    resultText.style.display = q ? "block" : "none";
    emptyBox.hidden = !(q && found === 0);
    resultText.textContent = found === 0 ? "No items found" : found + " menu item" + (found === 1 ? "" : "s") + " found";
  }
  input.addEventListener("input", searchMenu);
  clearBtn.addEventListener("click", function () {
    input.value = "";
    searchMenu();
    input.focus();
  });

  /* ---------- CATEGORY IMAGE TILES ---------- */
  const tiles = document.querySelectorAll(".cat-tile");
  const searchBox = document.querySelector(".search-box");

  function setActive(id) {
    tiles.forEach((t) => t.classList.toggle("active", t.dataset.target === id));
    const active = document.querySelector(".cat-tile.active");
    if (active) active.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  }

  tiles.forEach(function (tile) {
    tile.addEventListener("click", function (e) {
      e.preventDefault();
      const id = tile.dataset.target;
      if (tile.classList.contains("active")) {
        /* tap the selected tile again = back to the top of the menu */
        tiles.forEach((t) => t.classList.remove("active"));
        $("menuContent").scrollIntoView({ behavior: "smooth" });
        return;
      }
      const target = $(id);
      const top = target.getBoundingClientRect().top + window.scrollY - (searchBox.offsetHeight + 4);
      window.scrollTo({ top: top, behavior: "smooth" });
      setActive(id);
    });
  });

  if ("IntersectionObserver" in window && sections.length) {
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting && window.scrollY > 300) setActive(en.target.id);
      });
    }, { rootMargin: "-25% 0px -65% 0px" });
    sections.forEach((s) => io.observe(s));
  }

  /* ---------- SHARE ---------- */
  const toast = $("toast");
  let toastTimer;
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
  }

  document.querySelectorAll(".share-btn").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      const text = btn.dataset.name + " - \u20B9" + btn.dataset.price + "\nCheck it out on the Creamy Creations menu!";
      if (navigator.share) {
        try { await navigator.share({ title: btn.dataset.name, text: text, url: location.href }); } catch (err) {}
      } else {
        try {
          await navigator.clipboard.writeText(text + "\n" + location.href);
          showToast("Menu link copied");
        } catch (err) {
          showToast("Share is not available");
        }
      }
    });
  });
});