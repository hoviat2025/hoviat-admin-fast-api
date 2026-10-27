// Staging/test sender bot Worker.
// Configure the Telegram webhook for the test sender bot to point to this Worker.
// This Worker intentionally calls the staging API, never the production hostname.

// Set WEBHOOK_SECRET to the secret_token used for Telegram setWebhook.
// Set API_SECRET to the staging backend's SENDER_WEBHOOK_API_SECRET.
const WEBHOOK_SECRET = "";
const API_SECRET = "";
const STAGING_API_ORIGIN = "https://sns-admin-stage.185.202.113.95.nip.io";

// Test source channel: forwarded messages containing the add_user marker.
const TEST_SOURCE_CHANNEL_ID = -1003941932759;
const MAIN_GROUP_ID = -1003741849641;
// Test Eurobot sender/reply channel and test source channel.
const PUBLIC_CHANNEL_ID = -1003997195070;
const PUBLIC_GROUP_ID = -1003915100291;
// Test Hilfen sender/reply channel and test source channel.
const HILFEN_CHANNEL_ID = -1003872442653;
const HILFEN_GROUP_ID = -1003946251854;

// TEMP DIAGNOSTIC: log the full update for anything touching the public
// channel/group so we can see the real Telegram fields. Enable only temporarily.
const DEBUG_PUBLIC_UPDATES = false;
// Temporary targeted diagnostic for legacy forwarding fields, without full updates.
const DEBUG_MATCHING = false;

// WARNING: historical _test endpoint names also exist in production.
// Staging isolation comes from STAGING_API_ORIGIN, not the _test suffix.

export default {
  async fetch(request) {
    console.log("Incoming request from Telegram");

    if (request.method !== "POST") {
      return new Response("OK");
    }

    if (
      !/^[A-Za-z0-9_-]{1,256}$/.test(WEBHOOK_SECRET) ||
      !API_SECRET ||
      API_SECRET.trim() !== API_SECRET ||
      /[\r\n]/.test(API_SECRET)
    ) {
      console.error("Sender webhook secrets are missing or invalid");
      return new Response("Webhook is not configured", { status: 503 });
    }

    const suppliedSecret = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (!suppliedSecret || !(await secretsMatch(suppliedSecret, WEBHOOK_SECRET))) {
      return new Response("Unauthorized", { status: 401 });
    }

    let update;
    try {
      update = await request.json();
    } catch (error) {
      console.error("Failed to parse Telegram JSON:", error);
      return new Response("bad json", { status: 400 });
    }

    const msg = update.message;
    if (!msg) {
      console.log("Ignored: not a message update");
      return new Response("ok");
    }

    if (
      DEBUG_PUBLIC_UPDATES &&
      (
        msg.sender_chat?.id === PUBLIC_CHANNEL_ID ||
        msg.forward_from_chat?.id === PUBLIC_CHANNEL_ID ||
        msg.forward_origin?.chat?.id === PUBLIC_CHANNEL_ID ||
        msg.chat?.id === PUBLIC_GROUP_ID ||
        msg.external_reply?.origin?.chat?.id === PUBLIC_CHANNEL_ID
      )
    ) {
      console.log("PUBLIC_UPDATE_RAW:", JSON.stringify(update));
    }

    if (DEBUG_MATCHING) {
      console.log("SENDER_MATCHING:", JSON.stringify({
        chat_id: msg.chat?.id,
        sender_chat_id: msg.sender_chat?.id,
        is_automatic_forward: msg.is_automatic_forward,
        has_forward_from_chat: Object.hasOwn(msg, "forward_from_chat"),
        forward_from_chat_id: msg.forward_from_chat?.id,
        has_forward_origin: Object.hasOwn(msg, "forward_origin"),
        forward_origin_chat_id: msg.forward_origin?.chat?.id,
        external_reply_origin_chat_id: msg.external_reply?.origin?.chat?.id,
      }));
    }

    if (
      msg.is_automatic_forward &&
      msg.sender_chat?.id === TEST_SOURCE_CHANNEL_ID &&
      msg.forward_from_chat?.id === TEST_SOURCE_CHANNEL_ID &&
      msg.chat?.id === MAIN_GROUP_ID
    ) {
      const text = msg.text || msg.caption || "";
      const match = text.match(/\$%\^(\d+)\^\$%add_user/);

      if (match) {
        const payload = {
          extracted_user_id: match[1],
          original_update: update,
        };

        await sendToApi(
          `${STAGING_API_ORIGIN}/webhook/hoviat/v1/eurobot/set_group_message_id_test`,
          payload,
        );
        return new Response("ok");
      }
    }

    const senderId = msg.sender_chat?.id;
    const originId = msg.external_reply?.origin?.chat?.id;

    if (
      senderId === PUBLIC_CHANNEL_ID &&
      originId === TEST_SOURCE_CHANNEL_ID &&
      msg.chat?.id === PUBLIC_GROUP_ID
    ) {
      await sendToApi(
        `${STAGING_API_ORIGIN}/webhook/hoviat/v1/eurobot/set_public_message_id_test`,
        { original_update: update },
      );
      return new Response("ok");
    }

    if (
      senderId === HILFEN_CHANNEL_ID &&
      originId === TEST_SOURCE_CHANNEL_ID &&
      msg.chat?.id === HILFEN_GROUP_ID
    ) {
      await sendToApi(
        `${STAGING_API_ORIGIN}/webhook/hoviat/v1/hilfen/set_hilfen_message_id`,
        { original_update: update },
      );
      return new Response("ok");
    }

    console.log("Ignored: no staging sender-bot criteria matched");
    return new Response("ok");
  },
};

async function secretsMatch(supplied, expected) {
  const encoder = new TextEncoder();
  const [suppliedDigest, expectedDigest] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(supplied)),
    crypto.subtle.digest("SHA-256", encoder.encode(expected)),
  ]);
  return crypto.subtle.timingSafeEqual(suppliedDigest, expectedDigest);
}

async function sendToApi(url, payload) {
  try {
    const response = await fetch(url, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_SECRET}`,
      },
      body: JSON.stringify(payload),
    });

    console.log(`Staging API request ${url} returned ${response.status}`);
    if (!response.ok) {
      console.error("Staging API response:", await response.text());
    }
  } catch (error) {
    console.error("Failed to call staging API:", error);
  }
}
