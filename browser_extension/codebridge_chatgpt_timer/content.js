(() => {
  const MESSAGE_TYPE = "CODEBRIDGE_CHATGPT_TIMER";
  const CHECK_INTERVAL_MS = 100;
  const HEARTBEAT_INTERVAL_MS = 15000;

  let seenStopButton = false;
  let finishSent = false;
  let manualStopClicked = false;
  let observedRequestId = null;
  let snapshotInFlight = false;
  let pendingCompletion = null;

  function sendEvent(action, requestId = null) {
    chrome.runtime.sendMessage(
      {
        type: MESSAGE_TYPE,
        action,
        request_id: requestId,
      },
      (result) => {
        void chrome.runtime.lastError;
        if (action === "finish" || action === "cancel") {
          if (!result || !result.ok || !result.payload || !result.payload.applied) {
            pendingCompletion = { action, requestId };
          } else {
            pendingCompletion = null;
          }
        }
      }
    );
  }

  sendEvent("heartbeat");
  window.setInterval(
    () => sendEvent("heartbeat"),
    HEARTBEAT_INTERVAL_MS
  );

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
  function syncTimer() {
    if (snapshotInFlight) return;
    snapshotInFlight = true;
    chrome.runtime.sendMessage(
      { type: MESSAGE_TYPE, action: "snapshot" },
      (result) => {
        snapshotInFlight = false;
        if (chrome.runtime.lastError || !result || !result.ok) return;
        const timer = result.payload && result.payload.timer;
        if (!timer) return;
        if (timer.state === "RUNNING" && timer.claimed_by_codebridge) {
          observedRequestId = timer.request_id;
          if (pendingCompletion && pendingCompletion.requestId === observedRequestId
              && !findVisibleStopButton()) {
            const pending = pendingCompletion;
            pendingCompletion = null;
            sendEvent(pending.action, pending.requestId);
          }
        } else {
          observedRequestId = null;
          pendingCompletion = null;
        }
      }
    );
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

      const action = manualStopClicked ? "cancel" : "finish";
      if (observedRequestId) {
        sendEvent(action, observedRequestId);
      } else {
        pendingCompletion = null;
      }
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

  window.setInterval(checkGenerationState, CHECK_INTERVAL_MS);
  window.setInterval(syncTimer, 1000);
  syncTimer();
  checkGenerationState();
})();
