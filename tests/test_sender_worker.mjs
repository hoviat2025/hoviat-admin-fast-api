// Offline contract checks. Every fetch is replaced; no Telegram/API calls occur.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { timingSafeEqual, webcrypto } from "node:crypto";
import vm from "node:vm";
import test from "node:test";

const source = readFileSync(new URL("../scripts/cloudflare-workers/sender-bot-webhook.js", import.meta.url), "utf8");
const hookSecret = "offline_webhook_test";
const apiSecret = "offline_api_test";
const mainId = -1001129100618;
const mainGroup = -1002086581533;
const publicId = -1003443613002;
const publicGroup = -1003238310244;
const hilfenId = -1002026011030;
const hilfenGroup = -1002156702345;

function worker({ configured = true, status = 200, networkError = false } = {}) {
  const calls = [];
  let code = source.replace("export default {", "globalThis.worker = {");
  if (configured) {
    code = code.replace('const WEBHOOK_SECRET = "";', `const WEBHOOK_SECRET = "${hookSecret}";`)
      .replace('const API_SECRET = "";', `const API_SECRET = "${apiSecret}";`);
  }
  const context = vm.createContext({
    Request, Response, TextEncoder, TextDecoder, Uint8Array, AbortSignal,
    console: { log() {}, error() {} },
    crypto: { subtle: {
      digest: (...args) => webcrypto.subtle.digest(...args),
      // Workers' timingSafeEqual extension, backed by Node's native equivalent.
      timingSafeEqual: (a, b) => timingSafeEqual(Buffer.from(a), Buffer.from(b)),
    } },
    fetch: async (url, options) => {
      calls.push({ url, options });
      if (networkError) throw new Error("offline simulated failure");
      return new Response("{}", { status });
    },
  });
  vm.runInContext(code, context);
  return { fetch: context.worker.fetch, calls };
}

function request(update, { secret = hookSecret, body = JSON.stringify(update), headers = {} } = {}) {
  return new Request("https://sender.example.test/", {
    method: "POST", headers: { "Content-Type": "application/json", ...(secret === null ? {} : { "X-Telegram-Bot-Api-Secret-Token": secret }), ...headers }, body,
  });
}

function mainUpdate() {
  return { update_id: 1, message: {
    message_id: 20, chat: { id: mainGroup }, is_automatic_forward: true,
    sender_chat: { id: mainId }, forward_from_chat: { id: mainId },
    forward_origin: { chat: { id: mainId }, message_id: 10 },
    text: "$%^12345^$%add_user",
  } };
}

function replyUpdate(channel, group) {
  return { update_id: 2, message: {
    message_id: 30, chat: { id: group }, sender_chat: { id: channel },
    external_reply: { origin: { chat: { id: mainId } }, message_id: 10 },
    forward_origin: { chat: { id: channel }, message_id: 25 },
  } };
}

test("blank deployment secrets fail closed", async () => {
  const app = worker({ configured: false });
  assert.equal((await app.fetch(request(mainUpdate()))).status, 503);
  assert.equal(app.calls.length, 0);
});

test("missing/wrong webhook secret is rejected before JSON parsing or fetch", async () => {
  for (const secret of [null, "wrong"]) {
    const app = worker();
    assert.equal((await app.fetch(request(null, { secret, body: "not json" }))).status, 401);
    assert.equal(app.calls.length, 0);
  }
});

test("bad JSON and oversized bodies never reach the API", async () => {
  for (const body of ["not json", "null", "[]", "x".repeat(256 * 1024 + 1)]) {
    const app = worker();
    assert.equal((await app.fetch(request(null, { body }))).status, 400);
    assert.equal(app.calls.length, 0);
  }
});

test("non-message updates are acknowledged without fetching", async () => {
  const app = worker();
  assert.equal((await app.fetch(request({ update_id: 0 }))).status, 200);
  assert.equal(app.calls.length, 0);
});

test("three production mappings preserve paths and send the shared API password", async () => {
  const cases = [
    [mainUpdate(), "eurobot/set_group_message_id_test"],
    [replyUpdate(publicId, publicGroup), "eurobot/set_public_message_id_test"],
    [replyUpdate(hilfenId, hilfenGroup), "hilfen/set_hilfen_message_id"],
  ];
  for (const [update, path] of cases) {
    const app = worker();
    assert.equal((await app.fetch(request(update))).status, 200);
    assert.equal(app.calls.length, 1);
    const { url, options } = app.calls[0];
    assert.equal(url, `https://185.202.113.95.nip.io/webhook/hoviat/v1/${path}`);
    assert.equal(options.method, "PUT");
    assert.equal(options.headers.Authorization, `Bearer ${apiSecret}`);
    assert.equal(options.redirect, "manual");
    assert.deepEqual(JSON.parse(options.body).original_update, update);
    if (path.includes("set_group")) assert.equal(JSON.parse(options.body).extracted_user_id, "12345");
  }
});

test("wrong groups, senders and origins do not match", async () => {
  const cases = [mainUpdate(), replyUpdate(publicId, publicGroup), replyUpdate(hilfenId, hilfenGroup)];
  for (const original of cases) {
    for (const field of ["group", "sender"]) {
      const update = structuredClone(original);
      if (field === "group") update.message.chat.id = -100999;
      else update.message.sender_chat.id = -100999;
      const app = worker();
      assert.equal((await app.fetch(request(update))).status, 200);
      assert.equal(app.calls.length, 0);
    }
  }
  const update = replyUpdate(publicId, publicGroup);
  update.message.external_reply.origin.chat.id = -100999;
  const app = worker();
  await app.fetch(request(update));
  assert.equal(app.calls.length, 0);
});

test("legacy forward criterion stays unchanged; no guessed modern fallback", async () => {
  const update = mainUpdate();
  delete update.message.forward_from_chat;
  const app = worker();
  assert.equal((await app.fetch(request(update))).status, 200);
  assert.equal(app.calls.length, 0);
});

test("backend errors and redirects are retryable, not falsely acknowledged", async () => {
  for (const status of [301, 401, 404, 422, 500]) {
    const app = worker({ status });
    assert.equal((await app.fetch(request(mainUpdate()))).status, 503);
    assert.equal(app.calls.length, 1);
  }
});

test("network failures are retryable", async () => {
  const app = worker({ networkError: true });
  assert.equal((await app.fetch(request(mainUpdate()))).status, 503);
  assert.equal(app.calls.length, 1);
});
