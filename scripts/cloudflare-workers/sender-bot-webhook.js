export default {
  async fetch(request, env) {
    console.log("Incoming request from Telegram");

    // 1. Basic Method Check
    if (request.method !== "POST") {
      return new Response("OK");
    }

    // 2. Parse JSON
    let update;
    try {
      update = await request.json();
    } catch (err) {
      console.error("Failed to parse JSON:", err);
      return new Response("bad json");
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
    
    const TARGET_CHANNEL_ID_1 = -1001129100618;

    // Check: Is automatic forward, Sender is Target 1, Forward Source is Target 1
    if (
      msg.is_automatic_forward &&
      msg.sender_chat && msg.sender_chat.id === TARGET_CHANNEL_ID_1 &&
      msg.forward_from_chat && msg.forward_from_chat.id === TARGET_CHANNEL_ID_1
    ) {
      
      const text = msg.text || msg.caption || ""; 
      const pattern = /\$%\^(\d+)\^\$%add_user/;
      const match = text.match(pattern);

      if (match) {
        const extractedUserId = match[1];
        console.log(`Scenario 1 Met! Extracted User ID: ${extractedUserId}`);

        // OLD URL (Commented out)
        // const apiUrl = "https://hoviat-api-url.safaee1361.workers.dev/webhook/hoviat/v1/eurobot/set_group_message_id";
        
        // NEW DIRECT URL (TEST ENDPOINT)
        const apiUrl = "https://hoviat-admin-fast-api.onrender.com/webhook/hoviat/v1/eurobot/set_group_message_id_test";
        
        const payload = {
          extracted_user_id: extractedUserId,
          original_update: update
        };

        await sendToApi(env, apiUrl, payload);
        return new Response("ok");
      }
    }


    // ==================================================================
    // SCENARIO 2: External Reply Check (New Logic)
    // Sender: -1003443613002
    // Origin: -1001129100618
    // Target Endpoint: set_public_message_id
    // ==================================================================

    const SENDER_ID_2 = -1003443613002;
    const ORIGIN_ID_2 = -1001129100618;

    // Safe extraction using optional chaining (?.)
    const senderId = msg.sender_chat?.id;
    const originId = msg.external_reply?.origin?.chat?.id;

    if (senderId === SENDER_ID_2 && originId === ORIGIN_ID_2) {
      console.log("Scenario 2 Met! External reply criteria matched.");

      // OLD URL (Commented out)
      // const apiUrl = "https://hoviat-api-url.safaee1361.workers.dev/webhook/hoviat/v1/eurobot/set_public_message_id";

      // NEW DIRECT URL (TEST ENDPOINT)
      const apiUrl = "https://hoviat-admin-fast-api.onrender.com/webhook/hoviat/v1/eurobot/set_public_message_id_test";

      // Payload for Scenario 2
      const payload = {
        original_update: update
      };

      await sendToApi(env, apiUrl, payload);
      return new Response("ok");
    }

    // No criteria met
    console.log("Ignored: No matching criteria found");
    return new Response("ok");
  }
};

/**
 * Helper function to send data to the API
 * Updated to use standard fetch to the external URL
 */
async function sendToApi(env, url, payload) {
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
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    console.log(`API request to ${url} status:`, apiResponse.status);
  } catch (err) {
    console.error("Fetch failed:", err);
  }
}