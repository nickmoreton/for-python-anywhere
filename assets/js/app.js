export const STATUS_MESSAGES = ["Planning", "Building", "Refining"];

export function nextStatusIndex(currentIndex) {
  return (currentIndex + 1) % STATUS_MESSAGES.length;
}

export function shouldAnimate(prefersReducedMotion) {
  return !prefersReducedMotion;
}

function enhanceStatusMessage() {
  const statusMessage = document.querySelector("[data-status-message]");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");

  if (!statusMessage || !shouldAnimate(motionPreference.matches)) {
    return;
  }

  let currentIndex = STATUS_MESSAGES.length - 1;

  window.setInterval(() => {
    statusMessage.classList.add("is-changing");
    window.setTimeout(() => {
      currentIndex = nextStatusIndex(currentIndex);
      statusMessage.textContent = STATUS_MESSAGES[currentIndex];
      statusMessage.classList.remove("is-changing");
    }, 180);
  }, 2800);
}

if (typeof document !== "undefined") {
  document.documentElement.classList.add("js");
  enhanceStatusMessage();
}
