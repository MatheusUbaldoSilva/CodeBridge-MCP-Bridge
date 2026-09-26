const COMPANION_BASE = "http://127.0.0.1:8768";
const COMPANION_HEADER = "X-CodeBridge-Companion";
const COMPANION_HEADER_VALUE = "chatgpt-timer-v1";

async function sendTimerEvent(
  action,
  requestId,
  resumeManual = false
) {
  const response = await fetch(
    `${COMPANION_BASE}/v1/chatgpt/timer/${action}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        [COMPANION_HEADER]: COMPANION_HEADER_VALUE,
      },
      body: JSON.stringify({
        request_id: requestId || null,
        resume_manual: Boolean(resumeManual),
      }),
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(
      `CodeBridge Companion respondeu HTTP ${response.status}`
    );
  }

  return response.json();
}

chrome.runtime.onMessage.addListener(
  (message, sender, sendResponse) => {
    if (
      !message ||
      message.type !== "CODEBRIDGE_CHATGPT_TIMER"
    ) {
      return false;
    }

    const action = String(
      message.action || ""
    ).toLowerCase();

    if (
      !["start", "finish", "cancel", "reset"].includes(action)
    ) {
      sendResponse({
        ok: false,
        error: "invalid_action",
      });
      return false;
    }

    sendTimerEvent(
      action,
      message.requestId,
      Boolean(message.resumeManual)
    )
      .then((payload) => {
        sendResponse({
          ok: true,
          payload,
        });
      })
      .catch((error) => {
        sendResponse({
          ok: false,
          error: String(
            error && error.message
              ? error.message
              : error
          ),
        });
      });

    return true;
  }
);
