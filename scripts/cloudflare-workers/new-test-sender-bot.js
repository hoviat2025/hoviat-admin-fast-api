// Staging/test sender bot Worker.
// Configure the Telegram webhook for the test sender bot to point to this Worker.
// This Worker intentionally calls the staging API, never the production hostname.

const STAGING_API_ORIGIN = "https://staging.185.202.113.95.nip.io";

export default {
  async fetch(request) {
    console.log("Incoming request from Telegram");

    if (request.method !== "POST") {
      return new Response("OK");
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

    // Test source channel: forwarded messages containing the add_user marker.
    const TEST_SOURCE_CHANNEL_ID = -1003941932759;
    if (
      msg.is_automatic_forward &&
      msg.sender_chat?.id === TEST_SOURCE_CHANNEL_ID &&
      msg.forward_from_chat?.id === TEST_SOURCE_CHANNEL_ID
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

    // Test Eurobot sender/reply channel and test source channel.
    const TEST_EUROBOT_SENDER_ID = -1003997195070;
    const TEST_SOURCE_ID = -1003941932759;
    const senderId = msg.sender_chat?.id;
    const originId = msg.external_reply?.origin?.chat?.id;

    if (senderId === TEST_EUROBOT_SENDER_ID && originId === TEST_SOURCE_ID) {
      await sendToApi(
        `${STAGING_API_ORIGIN}/webhook/hoviat/v1/eurobot/set_public_message_id_test`,
        { original_update: update },
      );
      return new Response("ok");
    }

    // Test Hilfen sender/reply channel and test source channel.
    const TEST_HILFEN_SENDER_ID = -1003872442653;
    if (senderId === TEST_HILFEN_SENDER_ID && originId === TEST_SOURCE_ID) {
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

async function sendToApi(url, payload) {
  try {
    const response = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
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
