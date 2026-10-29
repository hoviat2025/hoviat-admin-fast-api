// No network calls: every upstream response is supplied by the test harness.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { webcrypto, timingSafeEqual } from "node:crypto";
import vm from "node:vm";
import test from "node:test";

const source = readFileSync(new URL("../scripts/cloudflare-workers/sns-login-bot-production.js", import.meta.url), "utf8");
const bindings = {
  BOT_TOKEN: "123456:fake-production-bot",
  API_SECRET: "fake-production-login-secret",
  WEBHOOK_SECRET: "fake-production-webhook-secret",
};

function harness(username = "hoviatloginbot") {
  const calls = [];
  const context = vm.createContext({
    Request, Response, Headers, URL, TextEncoder, TextDecoder,
    AbortController, setTimeout, clearTimeout,
    console: { log() {}, error() {} },
    crypto: { subtle: {
      digest: webcrypto.subtle.digest.bind(webcrypto.subtle),
      timingSafeEqual: (a, b) => timingSafeEqual(Buffer.from(a), Buffer.from(b)),
    } },
    fetch: async (url, options) => {
      calls.push({ url, options, body: JSON.parse(options.body) });
      if (url.endsWith("/getMe")) return Response.json({ ok: true, result: { username } });
      if (url === "https://185.202.113.95.nip.io/api/sns/auth/bot/request-login") {
        return Response.json({ data: { login_token: "fake-single-use-code" }, error: {} });
      }
      if (url.startsWith(`https://api.telegram.org/bot${bindings.BOT_TOKEN}/`)) {
        return Response.json({ ok: true, result: {} });
      }
      throw new Error("Unexpected upstream in isolated test");
    },
  });
  vm.runInContext(source.replace("export default", "globalThis.worker ="), context);
  return { worker: context.worker, calls };
}

function request(body, secret = bindings.WEBHOOK_SECRET) {
  return new Request("https://production-login.example/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Telegram-Bot-Api-Secret-Token": secret },
    body: JSON.stringify(body),
  });
}

const from = { id: 40, is_bot: false, first_name: "Test" };
const chat = { id: 40, type: "private" };

test("bad webhook secret is rejected before upstream calls", async () => {
  const { worker, calls } = harness();
  assert.equal((await worker.fetch(request({ message: { from, chat } }, "wrong"), bindings)).status, 401);
  assert.equal(calls.length, 0);
});

test("test-bot token cannot serve the production login Worker", async () => {
  const { worker, calls } = harness("hoviatlogintestbot");
  await worker.fetch(request({ message: { from, chat, text: "/start" } }), bindings);
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.endsWith("/getMe"));
});

test("production callback uses production API, existing login secret and production website", async () => {
  const { worker, calls } = harness();
  const response = await worker.fetch(request({ callback_query: {
    id: "fake-callback", data: "web_login", from, message: { chat },
  } }), bindings);
  assert.equal(response.status, 200);
  const mint = calls.find(call => call.url.endsWith("/api/sns/auth/bot/request-login"));
  assert.equal(mint.url, "https://185.202.113.95.nip.io/api/sns/auth/bot/request-login");
  assert.equal(mint.options.headers.Authorization, `Bearer ${bindings.API_SECRET}`);
  assert.equal(mint.options.redirect, "manual");
  assert.equal(mint.body.user_id, 40);
  const delivery = calls.find(call => call.url.endsWith("/sendMessage"));
  assert.equal(delivery.body.chat_id, 40);
  assert.equal(delivery.body.reply_markup.inline_keyboard[1][0].url, "https://app.185.202.113.95.nip.io/login");
});

test("group messages cannot request a production login", async () => {
  const { worker, calls } = harness();
  await worker.fetch(request({ message: { from, chat: { id: -1, type: "group" } } }), bindings);
  assert.equal(calls.length, 0);
});
