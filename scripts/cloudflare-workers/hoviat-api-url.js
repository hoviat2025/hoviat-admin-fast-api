// 1. YOUR REAL HOST
const PRIMARY_HOST = '185.202.113.95.nip.io';

// 2. YOUR BACKUP HOST (Commented out)
// const BACKUP_HOST = 'hoviat-admin-fast-api.onrender.com';

// --- HELPER FUNCTION FOR LOGGING ---
// Prints the start and end of large payloads to avoid Cloudflare's 256KB limit
function formatLongBody(bodyText) {
  if (!bodyText) return "";
  if (bodyText.length <= 2000) {
    return bodyText;
  }
  const start = bodyText.substring(0, 1000);
  const end = bodyText.substring(bodyText.length - 1000);
  return `${start}\n\n... [TRUNCATED! Original size: ${bodyText.length} chars. Middle hidden to prevent crash] ...\n\n${end}`;
}

// --- WORKER ---

addEventListener('fetch', event => {
  // Pass the 'event' object down so we can use event.waitUntil()
  event.respondWith(handleRequest(event.request, event));
});

async function handleRequest(request, event) {

  const requestId = crypto.randomUUID();
  const url = new URL(request.url);

  // clone request for backup (Commented out since backup is disabled)
  // const requestForBackup = request.clone();

  // ---- READ REQUEST BODY FOR LOGGING ----
  let requestBody = "";
  try {
    const reqClone = request.clone();
    requestBody = await reqClone.text(); // Extracts the body text here
  } catch (e) {
    requestBody = "[unreadable body]";
  }

  // =====================================================================
  // 🛠️ DEBUGGING: SEND A FULL COPY TO WEBHOOK.SITE 
  // =====================================================================
  if (requestBody && requestBody !== "[unreadable body]") {
    const webhookPromise = fetch("https://webhook.site/db202ed4-e0e3-47cb-ac1e-55b5e4273a39", {
      method: "POST",
      headers: {
        // Forward the original content type, fallback to json
        "Content-Type": request.headers.get("Content-Type") || "application/json"
      },
      body: requestBody
    }).catch(err => console.error("Webhook copy failed:", err));

    // event.waitUntil safely runs this in the background without slowing down the primary request
    if (event && event.waitUntil) {
      event.waitUntil(webhookPromise);
    }
  }
  // =====================================================================

  console.log("---- INCOMING REQUEST ----");
  console.log("Request ID:", requestId);
  console.log("Endpoint:", url.pathname);
  console.log("Full URL:", request.url);
  console.log("Method:", request.method);
  console.log("Headers:", Object.fromEntries(request.headers.entries()));
  
  // ✅ LOGS THE CONTENT OF THE REQUEST BODY HERE (Start & End)
  console.log("Body:", formatLongBody(requestBody));

  // modify host for primary
  url.hostname = PRIMARY_HOST;
  url.protocol = 'https:';
  url.port = '';
  const primaryRequest = new Request(url, request);

  try {
    console.log("Forwarding to PRIMARY:", PRIMARY_HOST);
    const response = await fetch(primaryRequest);

    // detect empty 200 response
    if (response.status === 200) {
      const responseClone = response.clone();
      const bodyText = await responseClone.text();

      if (!bodyText || bodyText.length === 0) {
        throw new Error("Primary returned empty body");
      }

      console.log("---- PRIMARY RESPONSE ----");
      console.log("Status:", response.status);
      console.log("Body:", formatLongBody(bodyText));

      return response;
    }

    // log non-200 responses
    const respClone = response.clone();
    const bodyText = await respClone.text();

    console.log("---- PRIMARY RESPONSE ----");
    console.log("Status:", response.status);
    console.log("Body:", formatLongBody(bodyText));

    return response;

  } catch (error) {
    console.error("PRIMARY FAILED:", error.message);

    /* 
    =========================================
    BACKUP SECTION COMMENTED OUT AS REQUESTED
    =========================================
    // ---- TRY BACKUP ----
    url.hostname = BACKUP_HOST;

    console.log("Forwarding to BACKUP:", BACKUP_HOST);

    const backupRequest = new Request(url, requestForBackup);
    const backupResponse = await fetch(backupRequest);

    const backupClone = backupResponse.clone();
    let backupBody = "";

    try {
      backupBody = await backupClone.text();
    } catch {
      backupBody = "[unreadable body]";
    }

    console.log("---- BACKUP RESPONSE ----");
    console.log("Status:", backupResponse.status);
    console.log("Body:", formatLongBody(backupBody));

    return backupResponse;
    */

    // Since backup is disabled, return a fallback error so the client doesn't hang forever
    return new Response(
      JSON.stringify({ error: `Primary Request Failed: ${error.message}` }), 
      { 
        status: 502,
        headers: { "Content-Type": "application/json" }
      }
    );
  }
}
