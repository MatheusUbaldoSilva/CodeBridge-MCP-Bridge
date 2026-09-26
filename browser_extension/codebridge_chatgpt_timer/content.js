(() => {
  const MESSAGE_TYPE = "CODEBRIDGE_CHATGPT_TIMER";
  const CHECK_INTERVAL_MS = 150;
  const FINISH_GRACE_MS = 650;
  const FALLBACK_STABLE_MS = 1400;

  let activeRequestId = null;
  let seenGenerating = false;
  let finishCandidateAt = null;
  let assistantBaseline = 0;
  let lastAssistantText = "";
  let lastAssistantChangeAt = 0;
  let lastUserMessageCount = 0;

  function newRequestId() {
    return (
      Date.now().toString(36)
      + "-"
      + Math.random().toString(36).slice(2, 10)
    );
  }

  function sendEvent(
    action,
    requestId,
    resumeManual = false
  ) {
    chrome.runtime.sendMessage(
      {
        type: MESSAGE_TYPE,
        action,
        requestId,
        resumeManual: Boolean(resumeManual),
      },
      () => {
        void chrome.runtime.lastError;
      }
    );
  }

  function composerExists(root = document) {
    return Boolean(
      root.querySelector(
        "#prompt-textarea,"
        + "textarea[data-id='root'],"
        + "textarea,"
        + "[contenteditable='true']"
      )
    );
  }

  function assistantMessages() {
    return Array.from(
      document.querySelectorAll(
        "[data-message-author-role='assistant']"
      )
    );
  }

  function userMessages() {
    return Array.from(
      document.querySelectorAll(
        "[data-message-author-role='user']"
      )
    );
  }

  function isComposerElement(element) {
    if (!(element instanceof Element)) {
      return false;
    }

    return Boolean(
      element.closest(
        "#prompt-textarea,"
        + "textarea[data-id='root'],"
        + "textarea,"
        + "[contenteditable='true']"
      )
    );
  }

  function composerText() {
    const element = document.querySelector(
      "#prompt-textarea,"
      + "textarea[data-id='root'],"
      + "textarea,"
      + "[contenteditable='true']"
    );

    if (!element) {
      return "";
    }

    if (
      element instanceof HTMLTextAreaElement
      || element instanceof HTMLInputElement
    ) {
      return element.value || "";
    }

    return (
      element.innerText
      || element.textContent
      || ""
    );
  }

  function isContinueMessage(text) {
    const normalized = String(
      text || ""
    )
      .trim()
      .toLowerCase()
      .replace(/[.!?]+$/g, "")
      .trim();

    return normalized === "continuar";
  }

  function isComposerSubmitButton(button) {
    if (!(button instanceof HTMLButtonElement)) {
      return false;
    }

    if (
      button.type === "submit"
      && button.closest("form")
      && composerExists(button.closest("form"))
    ) {
      return true;
    }

    return false;
  }

  function latestAssistantText() {
    const messages = assistantMessages();

    if (!messages.length) {
      return "";
    }

    return (
      messages[messages.length - 1].innerText
      || messages[messages.length - 1].textContent
      || ""
    );
  }

  function findStopButton() {
    const direct = document.querySelector(
      "button[data-testid='stop-button'],"
      + "button[data-testid*='stop' i]"
    );

    if (direct) {
      return direct;
    }

    const buttons = document.querySelectorAll(
      "button[aria-label],button[title]"
    );

    for (const button of buttons) {
      const label = (
        button.getAttribute("aria-label")
        || button.getAttribute("title")
        || ""
      ).toLowerCase();

      if (
        label.includes("stop")
        || label.includes("parar")
        || label.includes("interromper")
      ) {
        return button;
      }
    }

    return null;
  }

  function isSendButton(button) {
    if (!button) {
      return false;
    }

    const testId = (
      button.getAttribute("data-testid")
      || ""
    ).toLowerCase();

    if (
      testId === "send-button"
      || testId.includes("send")
    ) {
      return true;
    }

    const label = (
      button.getAttribute("aria-label")
      || button.getAttribute("title")
      || ""
    ).toLowerCase();

    return (
      label.includes("send")
      || label.includes("enviar")
    );
  }

  function isStopButton(button) {
    if (!button) {
      return false;
    }

    const activeStop = findStopButton();

    if (
      activeStop
      && button === activeStop
    ) {
      return true;
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

  function startTimer(resumeManual = false) {
    if (activeRequestId) {
      return;
    }

    activeRequestId = newRequestId();
    seenGenerating = false;
    finishCandidateAt = null;
    assistantBaseline = assistantMessages().length;
    lastAssistantText = latestAssistantText();
    lastAssistantChangeAt = performance.now();

    sendEvent(
      "start",
      activeRequestId,
      resumeManual
    );
  }

  function finishTimer(cancelled = false) {
    if (!activeRequestId) {
      return;
    }

    const requestId = activeRequestId;
    activeRequestId = null;
    seenGenerating = false;
    finishCandidateAt = null;

    sendEvent(
      cancelled ? "cancel" : "finish",
      requestId
    );
  }

  function detectNewUserMessage() {
    const count = userMessages().length;

    if (count < lastUserMessageCount) {
      lastUserMessageCount = count;
      return;
    }

    if (count > lastUserMessageCount) {
      lastUserMessageCount = count;

      if (!activeRequestId) {
        const messages = userMessages();
        const latest = messages.length
          ? (
              messages[messages.length - 1].innerText
              || messages[messages.length - 1].textContent
              || ""
            )
          : "";

        startTimer(
          isContinueMessage(latest)
        );
      }
    }
  }

  function checkGenerationState() {
    detectNewUserMessage();

    if (!activeRequestId) {
      return;
    }

    const now = performance.now();
    const stop = findStopButton();

    if (stop) {
      seenGenerating = true;
      finishCandidateAt = null;
    } else if (seenGenerating) {
      if (finishCandidateAt === null) {
        finishCandidateAt = now;
      } else if (
        now - finishCandidateAt
        >= FINISH_GRACE_MS
      ) {
        finishTimer(false);
        return;
      }
    }

    const messages = assistantMessages();
    const latestText = latestAssistantText();

    if (latestText !== lastAssistantText) {
      lastAssistantText = latestText;
      lastAssistantChangeAt = now;
    }

    if (
      !seenGenerating
      && messages.length > assistantBaseline
      && latestText
      && now - lastAssistantChangeAt
        >= FALLBACK_STABLE_MS
    ) {
      finishTimer(false);
    }
  }

  document.addEventListener(
    "keydown",
    (event) => {
      if (
        event.key === "Enter"
        && !event.shiftKey
        && !event.ctrlKey
        && !event.metaKey
        && !event.altKey
        && isComposerElement(event.target)
      ) {
        startTimer(
          isContinueMessage(composerText())
        );
      }
    },
    true
  );

  document.addEventListener(
    "submit",
    (event) => {
      const form = event.target;

      if (
        form instanceof Element
        && composerExists(form)
      ) {
        startTimer(
          isContinueMessage(composerText())
        );
      }
    },
    true
  );

  document.addEventListener(
    "click",
    (event) => {
      const target = (
        event.target instanceof Element
          ? event.target.closest("button")
          : null
      );

      if (!target) {
        return;
      }

      if (
        activeRequestId
        && isStopButton(target)
      ) {
        finishTimer(true);
        return;
      }

      if (
        isSendButton(target)
        || isComposerSubmitButton(target)
      ) {
        startTimer(
          isContinueMessage(composerText())
        );
      }
    },
    true
  );

  lastUserMessageCount = userMessages().length;

  const observer = new MutationObserver(
    () => {
      checkGenerationState();
    }
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
        "disabled"
      ]
    }
  );

  window.setInterval(
    checkGenerationState,
    CHECK_INTERVAL_MS
  );
})();
