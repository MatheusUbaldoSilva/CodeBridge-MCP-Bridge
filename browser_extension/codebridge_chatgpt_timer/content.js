(() => {
  const MESSAGE_TYPE = "CODEBRIDGE_CHATGPT_TIMER";
  const CHECK_INTERVAL_MS = 100;

  let seenStopButton = false;
  let finishSent = false;
  let manualStopClicked = false;

  function sendEvent(action) {
    chrome.runtime.sendMessage(
      {
        type: MESSAGE_TYPE,
        action,
      },
      () => {
        void chrome.runtime.lastError;
      }
    );
  }

  function isVisible(element) {
    if (!(element instanceof Element)) {
      return false;
    }

    const style = window.getComputedStyle(element);
    if (
      style.display === "none"
      || style.visibility === "hidden"
      || style.opacity === "0"
    ) {
      return false;
    }

    const rect = element.getBoundingClientRect();

    return (
      rect.width > 0
      && rect.height > 0
      && element.getClientRects().length > 0
    );
  }

  function looksLikeStopButton(button) {
    if (!(button instanceof HTMLButtonElement)) {
      return false;
    }

    const testId = (
      button.getAttribute("data-testid")
      || ""
    ).toLowerCase();
    const label = (
      button.getAttribute("aria-label")
      || button.getAttribute("title")
      || ""
    ).toLowerCase();

    return (
      testId.includes("stop")
      || label.includes("stop")
      || label.includes("parar")
      || label.includes("interromper")
    );
  }

  function findVisibleStopButton() {
    const buttons = document.querySelectorAll(
      "button"
    );

    for (const button of buttons) {
      if (
        isVisible(button)
        && looksLikeStopButton(button)
      ) {
        return button;
      }
    }

    return null;
  }
  function checkGenerationState() {
    const stopButton = findVisibleStopButton();

    if (stopButton) {
      seenStopButton = true;
      finishSent = false;
      return;
    }

    if (
      seenStopButton
      && !finishSent
    ) {
      finishSent = true;
      seenStopButton = false;

      sendEvent(
        manualStopClicked
          ? "cancel"
          : "finish"
      );
      manualStopClicked = false;
    }
  }

  document.addEventListener(
    "click",
    (event) => {
      const button = (
        event.target instanceof Element
          ? event.target.closest("button")
          : null
      );

      if (
        button
        && looksLikeStopButton(button)
        && isVisible(button)
      ) {
        manualStopClicked = true;
      }
    },
    true
  );

  const observer = new MutationObserver(
    checkGenerationState
  );

  observer.observe(
    document.documentElement,
    {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: [
        "aria-label",
        "data-testid",
        "style",
        "class",
        "hidden",
        "disabled",
      ],
    }
  );

  window.setInterval(
    checkGenerationState,
    CHECK_INTERVAL_MS
  );

  checkGenerationState();
})();
