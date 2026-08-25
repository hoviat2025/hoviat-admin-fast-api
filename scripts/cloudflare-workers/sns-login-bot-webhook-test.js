// SNS login bot Worker (TEST webhook).
// Talks to users in Farsi, mints short-lived website login tokens through the
// staging API, and delivers them to the user.
//
// Webhook setup (run once):
//   curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
//        -d "url=<this-worker-url>"

// ============================================================
// CONFIG - everything you may need to change is right here.
// ============================================================
const BOT_TOKEN = ""; // the login bot's own token from BotFather
const API_ORIGIN = "https://staging.185.202.113.95.nip.io"; // backend base URL, no trailing slash
const API_SECRET = ""; // shared secret; must equal LOGIN_BOT_API_SECRET on the backend
// ============================================================

const LOGIN_BUTTON = "web_login";

export default {
  async fetch(request) {
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

    try {
      // Button presses arrive as callback_query updates.
      if (update.callback_query) {
        await handleCallback(update.callback_query);
        return new Response("ok");
      }

      const msg = update.message;
      if (!msg || !msg.from) {
        return new Response("ok");
      }

      const text = (msg.text || "").trim();
      const from = msg.from;

      if (text === "/start") {
        await sendStartMessage(msg.chat.id);
        return new Response("ok");
      }

      // Any other text: nudge the user toward the login button.
      await sendMessage(msg.chat.id, {
        text: "برای ورود به سایت، دکمه زیر را بزنید:",
        reply_markup: buildLoginKeyboard(),
      });
      console.log(`Handled fallback text for user ${from.id}`);
    } catch (error) {
      console.error("Unhandled error while processing update:", error);
    }

    return new Response("ok");
  },
};

async function handleCallback(callbackQuery) {
  const chatId = callbackQuery.message?.chat?.id;
  if (!chatId) return;

  // Always close the loading spinner on the button, even on failure.
  const answer = async (text) => {
    try {
      await callTelegram("answerCallbackQuery", {
        callback_query_id: callbackQuery.id,
        text,
      });
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
    data = await requestLoginToken(from);
  } catch (error) {
    console.error("Login token request failed:", error);
    await answer("خطا در ارتباط با سرور");
    await sendMessage(chatId, {
      text: "خطایی رخ داد. لطفاً چند لحظه بعد دوباره تلاش کنید.",
    });
    return;
  }

  if (!data || !data.login_token) {
    await answer("دریافت کد ناموفق بود");
    await sendMessage(chatId, {
      text: "دریافت کد ورود ناموفق بود. لطفاً کمی بعد دوباره تلاش کنید.",
    });
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
  });
}

async function sendStartMessage(chatId) {
  await sendMessage(chatId, {
    text: [
      "سلام!",
      "",
      "این ربات برای ورود به وب‌سایت استفاده می‌شود.",
      "با زدن دکمه زیر یک کد یک‌بارمصرف دریافت می‌کنید",
      "که می‌توانید در صفحه ورود سایت وارد کنید.",
    ].join("\n"),
    reply_markup: buildLoginKeyboard(),
  });
}

function buildLoginKeyboard() {
  return JSON.stringify({
    inline_keyboard: [[{ text: "ورود به سایت", callback_data: LOGIN_BUTTON }]],
  });
}

// Calls POST /api/sns/auth/bot/request-login and unwraps the StandardResponse
// envelope ({ data, meta, error }).
async function requestLoginToken(from) {
  const url = `${API_ORIGIN}/api/sns/auth/bot/request-login`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_SECRET}`,
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
    console.error("request-login error body:", body);
    return null;
  }

  return body?.data ?? null;
}

async function sendMessage(chatId, options) {
  return callTelegram("sendMessage", {
    chat_id: chatId,
    ...options,
  });
}

async function callTelegram(method, payload) {
  const url = `https://api.telegram.org/bot${BOT_TOKEN}/${method}`;
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
