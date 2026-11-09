/*
 * Home page scroll scenes.
 * - Content is fully readable without this script (plain vertical flow).
 * - Desktop (≥1024px wide, ≥620px tall) without reduced motion: each [data-story]
 *   becomes a sticky scene whose step follows the scroll position. Scrolling back
 *   returns to earlier steps; the page scroll itself is never intercepted.
 * - [data-reveal] elements fade in once when they enter the viewport.
 */
(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const wide = matchMedia("(min-width: 1024px) and (min-height: 620px)");
  const stories = [...document.querySelectorAll("[data-story]")];
  let ticking = false;

  const pad = (n) => String(n).padStart(2, "0");

  function setStep(story, idx) {
    if (story.dataset.active === String(idx)) return;
    story.dataset.active = String(idx);
    const steps = story.querySelectorAll(".story-step");
    steps.forEach((step, i) => {
      step.dataset.state = i < idx ? "past" : i === idx ? "active" : "next";
      step.inert = i !== idx;                       // hidden steps cannot take keyboard focus
    });
    const count = story.querySelector(".story-count");
    if (count) count.textContent = `${pad(idx + 1)} / ${pad(steps.length)}`;
  }

  function reset(story) {
    delete story.dataset.active;
    story.style.removeProperty("--p");
    story.style.removeProperty("--progress");
    story.querySelectorAll(".story-step").forEach((step) => {
      delete step.dataset.state;
      step.inert = false;
    });
  }

  function update() {
    ticking = false;
    for (const story of stories) {
      if (!story.classList.contains("is-enhanced")) continue;
      const range = story.offsetHeight - window.innerHeight;
      const progress = Math.min(1, Math.max(0, -story.getBoundingClientRect().top / Math.max(range, 1)));
      const n = story.querySelectorAll(".story-step").length;
      const idx = Math.min(n - 1, Math.floor(progress * n));
      setStep(story, idx);
      story.style.setProperty("--p", (progress * n - idx).toFixed(3));
      story.style.setProperty("--progress", progress.toFixed(3));
    }
  }

  function requestUpdate() {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(update);
    }
  }

  function applyMode() {
    const enhanced = wide.matches && !reduce.matches;
    for (const story of stories) {
      story.classList.toggle("is-enhanced", enhanced);
      if (!enhanced) reset(story);
    }
    update();
  }

  function setupReveal() {
    if (reduce.matches || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          io.unobserve(entry.target);
        }
      }
    }, { rootMargin: "0px 0px -10% 0px" });
    document.querySelectorAll("[data-reveal]").forEach((el) => {
      el.classList.add("will-reveal");
      io.observe(el);
    });
  }

  addEventListener("scroll", requestUpdate, { passive: true });
  addEventListener("resize", requestUpdate);
  wide.addEventListener("change", applyMode);
  reduce.addEventListener("change", applyMode);
  applyMode();
  setupReveal();
})();
