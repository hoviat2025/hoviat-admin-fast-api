// PRODUCTION sender Worker. Edit deployment settings here, not throughout the file.
// Match WEBHOOK_SECRET to Telegram setWebhook's secret_token. Register it FIRST
// while the previous Worker still ignores that header, then deploy this version.
// Match API_SECRET to the backend's SENDER_WEBHOOK_API_SECRET before API cutover.
// Keep real values private; the repository intentionally contains blank secrets.
const WEBHOOK_SECRET = "";
const API_SECRET = "";
const API_ORIGIN = "https://185.202.113.95.nip.io";

const TARGET_CHANNEL_ID_1 = -1001129100618; // Main/source production channel.
const MAIN_GROUP_ID = -1002086581533;
const SENDER_ID_2 = -1003443613002; // Public production channel.
const ORIGIN_ID_2 = TARGET_CHANNEL_ID_1;
const PUBLIC_GROUP_ID = -1003238310244;
const SENDER_ID_3 = -1002026011030; // Hilfen production channel.
const ORIGIN_ID_3 = TARGET_CHANNEL_ID_1;
const HILFEN_GROUP_ID = -1002156702345;
const API_TIMEOUT_MS = 8000;
const MAX_UPDATE_BYTES = 256 * 1024;

// WARNING: `_test` is a historical name also used by PRODUCTION endpoints.
// The API origin, real channel IDs and groups determine the target environment.

export default {
  async fetch(request) {
    console.log("Incoming request from Telegram");

    // 1. Basic Method Check
    if (request.method !== "POST") {
      return new Response("OK");
    }

    if (!/^[A-Za-z0-9_-]{1,256}$/.test(WEBHOOK_SECRET) ||
        !API_SECRET || API_SECRET.trim() !== API_SECRET || /[\r\n]/.test(API_SECRET)) {
      console.error("Sender webhook settings are missing or invalid");
      return new Response("Webhook is not configured", { status: 503 });
    }
    // Verify Telegram before parsing an update or calling the backend.
    const suppliedSecret = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (!suppliedSecret || !(await secretsMatch(suppliedSecret, WEBHOOK_SECRET))) {
      return new Response("Unauthorized", { status: 401 });
    }

    // 2. Parse JSON (bounded before parsing, even without Content-Length).
    let update;
    try {
      update = await readUpdate(request);
      if (!update || typeof update !== "object" || Array.isArray(update)) {
        return new Response("bad json", { status: 400 });
      }
    } catch (err) {
      console.error("Failed to parse JSON");
      return new Response("bad json", { status: 400 });
    }

    // We only care about 'message' updates
    const msg = update.message;
    if (!msg) {
      console.log("Ignored: Not a message update");
      return new Response("ok");
    }

    // ==================================================================
    // SCENARIO 1: Automatic Forward + Regex (Original Logic)
    // Target: -1001129100618 -> set_group_message_id
    // ==================================================================

    // Check: Is automatic forward, Sender is Target 1, Forward Source is Target 1
    // Preserve the known production forward_from_chat criterion. Any modern
    // field fallback requires a separately observed real update before changing it.
    if (
      msg.is_automatic_forward &&
      msg.sender_chat?.id === TARGET_CHANNEL_ID_1 &&
      msg.forward_from_chat?.id === TARGET_CHANNEL_ID_1 &&
      msg.chat?.id === MAIN_GROUP_ID
    ) {
      const text = msg.text || msg.caption || "";
      const pattern = /\$%\^(\d+)\^\$%add_user/;
      const match = typeof text === "string" ? text.match(pattern) : null;

      if (match) {
        const extractedUserId = match[1];
        console.log("Scenario 1 Met! Extracted user marker.");

        // OLD URL (Commented out)
        // const apiUrl = "https://hoviat-api-url.safaee1361.workers.dev/webhook/hoviat/v1/eurobot/set_group_message_id";

        // DIRECT PRODUCTION URL (historical `_test` endpoint name).
        const apiUrl = `${API_ORIGIN}/webhook/hoviat/v1/eurobot/set_group_message_id_test`;
        const payload = {
          extracted_user_id: extractedUserId,
          original_update: update
        };

        return sendToApi(apiUrl, payload);
      }
    }

    // ==================================================================
    // SCENARIO 2: External Reply Check (New Logic)
    // Sender: -1003443613002
    // Origin: -1001129100618
    // Target Endpoint: set_public_message_id
    // ==================================================================

    // Safe extraction using optional chaining (?.)
    const senderId = msg.sender_chat?.id;
    const originId = msg.external_reply?.origin?.chat?.id;

    if (senderId === SENDER_ID_2 && originId === ORIGIN_ID_2 && msg.chat?.id === PUBLIC_GROUP_ID) {
      console.log("Scenario 2 Met! External reply criteria matched.");

      // OLD URL (Commented out)
      // const apiUrl = "https://hoviat-api-url.safaee1361.workers.dev/webhook/hoviat/v1/eurobot/set_public_message_id";

      // DIRECT PRODUCTION URL (historical `_test` endpoint name).
      const apiUrl = `${API_ORIGIN}/webhook/hoviat/v1/eurobot/set_public_message_id_test`;

      // Payload for Scenario 2
      const payload = { original_update: update };
      return sendToApi(apiUrl, payload);
    }

    // ==================================================================
    // SCENARIO 3: Hilfen Channel External Reply
    // Sender: -1002026011030
    // Origin: -1001129100618
    // Target Endpoint: set_hilfen_message_id
    // ==================================================================

    if (senderId === SENDER_ID_3 && originId === ORIGIN_ID_3 && msg.chat?.id === HILFEN_GROUP_ID) {
      console.log("Scenario 3 Met! Hilfen external reply criteria matched.");

      const apiUrl = `${API_ORIGIN}/webhook/hoviat/v1/hilfen/set_hilfen_message_id`;
      const payload = { original_update: update };
      return sendToApi(apiUrl, payload);
    }

    // No criteria met
    console.log("Ignored: No matching criteria found");
    return new Response("ok");
  }
};

async function secretsMatch(supplied, expected) {
  const encoder = new TextEncoder();
  const [left, right] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(supplied)),
    crypto.subtle.digest("SHA-256", encoder.encode(expected)),
  ]);
  return crypto.subtle.timingSafeEqual(left, right);
}

async function readUpdate(request) {
  if (Number(request.headers.get("Content-Length")) > MAX_UPDATE_BYTES) throw new Error("Too large");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("No update");
  const parts = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_UPDATE_BYTES) {
        await reader.cancel();
        throw new Error("Too large");
      }
      parts.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) { bytes.set(part, offset); offset += part.byteLength; }
  return JSON.parse(new TextDecoder().decode(bytes));
}

/**
 * Helper function to send data to the API
 * Updated to use standard fetch to the external URL
 */
async function sendToApi(url, payload) {
  try {
    // ============================================================
    // PREVIOUS BINDING CODE (COMMENTED OUT)
    // ============================================================
    /*
    const apiResponse = await env.HOVIAT_API.fetch(url, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    */

    // ============================================================
    // NEW DIRECT FETCH CODE
    // ============================================================
    const apiResponse = await fetch(url, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_SECRET}`,
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
      // Never forward the API password to a redirect destination.
      redirect: "manual",
    });

    console.log("Sender API status:", apiResponse.status);
    const accepted = apiResponse.ok;
    await apiResponse.body?.cancel();
    // A failed or ambiguous delivery must remain retryable by Telegram.
    // Backend mapping upserts tolerate repeated delivery of the same update.
    return new Response(accepted ? "ok" : "Backend unavailable", { status: accepted ? 200 : 503 });
  } catch (err) {
    // Do not log fetch exceptions: they can contain a request URL or headers.
    console.error("Sender API request failed");
    return new Response("Backend unavailable", { status: 503 });
  }
}
