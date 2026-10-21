// SNS login bot Worker (TEST webhook).
// Talks to users in Farsi, mints short-lived website login tokens through the
// staging API, and delivers them to the user.
//
// Deployment requires matching WEBHOOK_SECRET and setWebhook.secret_token.
// See the adjacent .md for the coordinated rollout; no unauthenticated fallback.

// ============================================================
// CONFIG - blank legacy inline fallback. Worker secret bindings are preferred.
// ============================================================
const BOT_TOKEN = ""; // the login bot's own token from BotFather
const API_ORIGIN = "https://staging.185.202.113.95.nip.io"; // backend base URL, no trailing slash
const API_SECRET = ""; // shared secret; must equal LOGIN_BOT_API_SECRET on the backend
const WEBHOOK_SECRET = ""; // separate random credential; also set as Telegram setWebhook.secret_token
// ============================================================

const LOGIN_BUTTON = "web_login";

export default {
  async fetch(request, env = {}) {
    const config = {
      botToken: env.BOT_TOKEN ?? BOT_TOKEN,
      apiOrigin: env.API_ORIGIN ?? API_ORIGIN,
      apiSecret: env.API_SECRET ?? API_SECRET,
      webhookSecret: env.WEBHOOK_SECRET ?? WEBHOOK_SECRET,
    };
    // Reject before JSON parsing or any backend/Telegram call. Empty checkout
    // credentials deliberately leave this endpoint unavailable.
    if (!configurationReady(config)) {
      return new Response("webhook not configured", { status: 503 });
    }
    if (request.method !== "POST") {
      return new Response("method not allowed", { status: 405, headers: { Allow: "POST" } });
    }

    let authenticated = false;
    try {
      authenticated = await authenticateWebhook(request, config.webhookSecret);
    } catch {
      console.error("Webhook authentication unavailable");
      return new Response("webhook authentication unavailable", { status: 503 });
    }
    if (!authenticated) {
      return new Response("unauthorized", { status: 401 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      console.error("Failed to parse authenticated Telegram JSON");
      return new Response("bad json", { status: 400 });
    }
    if (!update || typeof update !== "object" || Array.isArray(update)) {
      return new Response("bad update", { status: 400 });
    }

    try {
      // Button presses arrive as callback_query updates.
      if (update.callback_query) {
        await handleCallback(update.callback_query, config);
        return new Response("ok");
      }

      const msg = update.message;
      if (!msg || !isOwnPrivateChat(msg.chat, msg.from)) {
        return new Response("ok");
      }

      const text = typeof msg.text === "string" ? msg.text.trim() : "";
      const from = msg.from;

      if (text === "/start") {
        await sendStartMessage(msg.chat.id, config);
        return new Response("ok");
      }

      // Any other text: nudge the user toward the login button.
      await sendMessage(msg.chat.id, {
        text: "برای ورود به سایت، دکمه زیر را بزنید:",
        reply_markup: buildLoginKeyboard(),
      }, config);
      console.log(`Handled fallback text for user ${from.id}`);
    } catch (error) {
      console.error("Unhandled error while processing update:", error);
    }

    return new Response("ok");
  },
};

function configurationReady(config) {
  return Boolean(
    config.botToken && config.apiSecret &&
    /^[A-Za-z0-9_-]{1,256}$/.test(config.webhookSecret) &&
    config.webhookSecret !== config.apiSecret && config.webhookSecret !== config.botToken
  );
}

async function authenticateWebhook(request, expectedSecret) {
  const received = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
  if (!received || !/^[A-Za-z0-9_-]{1,256}$/.test(received)) return false;
  // Equal-sized digests allow the Workers-native constant-time comparison
  // without revealing where credentials differ or comparing unequal buffers.
  const encoder = new TextEncoder();
  const [expectedDigest, receivedDigest] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(expectedSecret)),
    crypto.subtle.digest("SHA-256", encoder.encode(received)),
  ]);
  return crypto.subtle.timingSafeEqual(expectedDigest, receivedDigest);
}

function isOwnPrivateChat(chat, actor) {
  return chat?.type === "private" && actor?.is_bot !== true &&
    Number.isSafeInteger(actor?.id) && actor.id > 0 &&
    actor.id === chat.id;
}

async function handleCallback(callbackQuery, config) {
  // A group/inline callback must never mint a token or deliver it to others.
  // Use the button presser's ID, not the bot that authored the button message.
  if (!isOwnPrivateChat(callbackQuery?.message?.chat, callbackQuery?.from)) return;
  const chatId = callbackQuery.message?.chat?.id;

  // Always close the loading spinner on the button, even on failure.
  const answer = async (text) => {
    try {
      await callTelegram("answerCallbackQuery", {
        callback_query_id: callbackQuery.id,
        text,
      }, config);
    } catch (error) {
      console.error("answerCallbackQuery failed:", error);
    }
  };

  if (callbackQuery.data !== LOGIN_BUTTON) {
    await answer("");
    return;
  }

  const from = callbackQuery.from;
  let data;
  try {
    data = await requestLoginToken(from, config);
  } catch (error) {
    console.error("Login token request failed:", error);
    await answer("خطا در ارتباط با سرور");
    await sendMessage(chatId, {
      text: "خطایی رخ داد. لطفاً چند لحظه بعد دوباره تلاش کنید.",
    }, config);
    return;
  }

  if (!data || !data.login_token) {
    await answer("دریافت کد ناموفق بود");
    await sendMessage(chatId, {
      text: "دریافت کد ورود ناموفق بود. لطفاً کمی بعد دوباره تلاش کنید.",
    }, config);
    return;
  }

  const minutes = Math.max(1, Math.round((data.expires_in || 300) / 60));
  await answer("کد ورود ساخته شد");
  await sendMessage(chatId, {
    text: [
      "کد ورود شما:",
      "",
      `\`${data.login_token}\``,
      "",
      `این کد ${minutes} دقیقه اعتبار دارد و فقط یک بار قابل استفاده است.`,
      "آن را در صفحه ورود سایت وارد کنید.",
    ].join("\n"),
  }, config);
}

async function sendStartMessage(chatId, config) {
  await sendMessage(chatId, {
    text: [
      "سلام!",
      "",
      "این ربات برای ورود به وب‌سایت استفاده می‌شود.",
      "با زدن دکمه زیر یک کد یک‌بارمصرف دریافت می‌کنید",
      "که می‌توانید در صفحه ورود سایت وارد کنید.",
    ].join("\n"),
    reply_markup: buildLoginKeyboard(),
  }, config);
}

function buildLoginKeyboard() {
  return JSON.stringify({
    inline_keyboard: [[{ text: "ورود به سایت", callback_data: LOGIN_BUTTON }]],
  });
}

// Calls POST /api/sns/auth/bot/request-login and unwraps the StandardResponse
// envelope ({ data, meta, error }).
async function requestLoginToken(from, config) {
  const url = `${config.apiOrigin}/api/sns/auth/bot/request-login`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiSecret}`,
    },
    body: JSON.stringify({
      user_id: from.id,
      first_name: from.first_name || undefined,
      last_name: from.last_name || undefined,
      username: from.username || undefined,
    }),
  });

  console.log(`request-login returned ${response.status}`);

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    console.error(`request-login failed with status ${response.status}`);
    return null;
  }

  return body?.data ?? null;
}

async function sendMessage(chatId, options, config) {
  return callTelegram("sendMessage", {
    chat_id: chatId,
    ...options,
  }, config);
}

async function callTelegram(method, payload, config) {
  const url = `https://api.telegram.org/bot${config.botToken}/${method}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    console.error(`Telegram ${method} returned ${response.status}:`, await response.text());
  }

  return response;
}
