// EDIT SETTINGS HERE in Cloudflare's code editor. Fill the three empty strings.
const SETTINGS = {
  BOT_TOKEN: "", // Paste the NEW TEST bot's BotFather token here.
  API_SECRET: "", // Staging backend's LOGIN_BOT_API_SECRET.
  WEBHOOK_SECRET: "", // Same password used when registering Telegram's webhook.
  API_ORIGIN: "https://sns-admin-stage.185.202.113.95.nip.io",
  WEBSITE_URL: "https://sns-stage.185.202.113.95.nip.io/login",
};

// Cloudflare bindings are optional; if present, they override the values above.
function config(env) {
  return {
    apiOrigin: env.API_ORIGIN ?? SETTINGS.API_ORIGIN,
    botToken: env.BOT_TOKEN ?? SETTINGS.BOT_TOKEN,
    apiSecret: env.API_SECRET ?? SETTINGS.API_SECRET,
    webhookSecret: env.WEBHOOK_SECRET ?? SETTINGS.WEBHOOK_SECRET,
    websiteUrl: env.WEBSITE_URL ?? SETTINGS.WEBSITE_URL,
  };
}
const LOGIN_CALLBACK = "web_login";
const TELEGRAM_TIMEOUT_MS = 5000;
const API_TIMEOUT_MS = 8000;
const BODY_TIMEOUT_MS = 5000;
const MAX_BODY_BYTES = 32 * 1024;
// WEBHOOK_SECRET accepts Telegram's 1..256 A-Z/a-z/0-9/_/- characters.
// Use a separate, randomly generated value; do not reuse API_SECRET or BOT_TOKEN.
// No storage/deduplication is configured: repeated button presses can mint tokens.

export default {
  async fetch(request, env = {}) {
    if (request.method === "GET") return reply("OK");
    if (request.method !== "POST") {
      return reply("method not allowed", 405, { Allow: "GET, POST" });
    }
    const settings = config(env);
    if (!configurationReady(settings)) return reply("unavailable", 503);

    try {
      if (!(await authenticateWebhook(request, settings.webhookSecret))) {
        return reply("unauthorized", 401);
      }
    } catch {
      return reply("unavailable", 503);
    }

    // Authenticate before reading any untrusted body or making outbound calls.
    let update;
    try {
      update = await readJson(request, BODY_TIMEOUT_MS);
      if (!update || typeof update !== "object" || Array.isArray(update)) {
        return reply("bad update", 400);
      }
    } catch {
      return reply("bad update", 400);
    }

    if (update.callback_query) {
      const callback = update.callback_query;
      if (callback.data !== LOGIN_CALLBACK ||
          !isOwnPrivateChat(callback.message?.chat, callback.from) ||
          typeof callback.id !== "string" || !callback.id) return reply("OK");
      await handleLogin(callback, settings);
    } else if (isOwnPrivateChat(update.message?.chat, update.message?.from)) {
      const chatId = update.message.chat.id;
      try {
        await sendMessage(chatId, {
          text: "سلام! برای دریافت کد یک‌بارمصرف ورود به سایت، دکمه زیر را بزنید.",
          reply_markup: loginKeyboard(),
        }, settings);
      } catch {
        await sendRetry(chatId, settings);
      }
    }
    // Avoid automatic replay after an ambiguous token mint/delivery failure.
    // Users can explicitly retry via the button; this does not deduplicate updates.
    return reply("OK");
  },
};

function reply(text, status = 200, headers = {}) {
  return new Response(text, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", ...headers },
  });
}

function configurationReady(settings) {
  const nonempty = (value) => typeof value === "string" && value.trim().length > 0;
  if (!nonempty(settings.botToken) || !nonempty(settings.apiSecret) ||
      typeof settings.webhookSecret !== "string" ||
      !/^[A-Za-z0-9_-]{1,256}$/.test(settings.webhookSecret) ||
      settings.webhookSecret === settings.apiSecret ||
      settings.webhookSecret === settings.botToken) return false;
  try {
    const api = new URL(settings.apiOrigin);
    const website = new URL(settings.websiteUrl);
    return api.protocol === "https:" && website.protocol === "https:" &&
      !api.username && !api.password && !api.search && !api.hash &&
      api.pathname === "/" && !website.username && !website.password;
  } catch {
    return false;
  }
}

async function authenticateWebhook(request, expected) {
  const received = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
  if (!received || !/^[A-Za-z0-9_-]{1,256}$/.test(received)) return false;
  const encoder = new TextEncoder();
  const [left, right] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(expected)),
    crypto.subtle.digest("SHA-256", encoder.encode(received)),
  ]);
  // Workers extension: compare equal-sized buffers in constant time.
  return crypto.subtle.timingSafeEqual(left, right);
}

function isOwnPrivateChat(chat, actor) {
  return chat?.type === "private" && actor?.is_bot === false &&
    Number.isSafeInteger(actor.id) && actor.id > 0 && chat.id === actor.id;
}

function loginKeyboard() {
  return { inline_keyboard: [[{ text: "دریافت کد ورود", callback_data: LOGIN_CALLBACK }]] };
}

async function handleLogin(callback, settings) {
  const chatId = callback.from.id;
  try {
    // Close Telegram's spinner before waiting for the backend.
    await telegram("answerCallbackQuery", {
      callback_query_id: callback.id,
      text: "در حال دریافت کد ورود…",
    }, settings);
    const from = callback.from;
    const body = await fetchJson(
      `${new URL(settings.apiOrigin).origin}/api/sns/auth/bot/request-login`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${settings.apiSecret}`,
        },
        body: JSON.stringify({
          user_id: from.id,
          first_name: typeof from.first_name === "string" ? from.first_name : undefined,
          last_name: typeof from.last_name === "string" ? from.last_name : undefined,
          username: typeof from.username === "string" ? from.username : undefined,
        }),
      },
      API_TIMEOUT_MS,
    );
    const token = body?.data?.login_token;
    // Telegram copy_text supports 1..256 characters. Never send malformed tokens.
    const hasError = body?.error && Object.keys(body.error).length > 0;
    if (hasError || typeof token !== "string" || !token.length || token.length > 256) {
      throw new Error("invalid login response");
    }
    await sendMessage(chatId, {
      text: `کد ورود شما:\n\n${token}\n\nاین کد یک‌بارمصرف و کوتاه‌مدت است. آن را در صفحه ورود سایت وارد کنید و در اختیار دیگران نگذارید.`,
      reply_markup: {
        inline_keyboard: [
          [{ text: "کپی کد ورود", copy_text: { text: token } }],
          [{ text: "باز کردن سایت", url: settings.websiteUrl }],
        ],
      },
    }, settings);
  } catch {
    // Never log tokens, credentials, Telegram URLs, response bodies or exceptions.
    await sendRetry(chatId, settings);
  }
}

async function sendRetry(chatId, settings) {
  try {
    await sendMessage(chatId, {
      text: "دریافت یا ارسال کد ورود ناموفق بود. لطفاً چند لحظه بعد دوباره دکمه دریافت کد ورود را بزنید. اگر دکمه را نمی‌بینید، /start را بفرستید.",
      reply_markup: loginKeyboard(),
    }, settings);
  } catch {
    // Telegram may also be unavailable. Acknowledge the update without replay.
  }
}

async function sendMessage(chatId, payload, settings) {
  return telegram("sendMessage", { chat_id: chatId, ...payload }, settings);
}

async function telegram(method, payload, settings) {
  const body = await fetchJson(`https://api.telegram.org/bot${settings.botToken}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }, TELEGRAM_TIMEOUT_MS);
  if (body?.ok !== true) throw new Error("Telegram request failed");
  return body.result;
}

async function fetchJson(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      redirect: "error",
    });
    if (!response.ok) {
      await response.body?.cancel();
      throw new Error("upstream request failed");
    }
    return await readJson(response, timeoutMs);
  } finally {
    clearTimeout(timer);
  }
}

async function readJson(message, timeoutMs) {
  const declared = message.headers.get("Content-Length");
  if (declared && Number(declared) > MAX_BODY_BYTES) {
    await message.body?.cancel();
    throw new Error("body too large");
  }
  if (!message.body) throw new Error("empty body");
  const reader = message.body.getReader();
  let timer;
  try {
    const read = async () => {
      const chunks = [];
      let length = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > MAX_BODY_BYTES) throw new Error("body too large");
        chunks.push(value);
      }
      const bytes = new Uint8Array(length);
      let offset = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.byteLength;
      }
      return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    };
    return await Promise.race([
      read(),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("body timeout")), timeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
