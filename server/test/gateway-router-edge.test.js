import assert from "node:assert/strict";
import { test } from "node:test";
import { GatewayRouter } from "../src/gateway/router.js";
import {
  InMemoryAttemptRepository,
  InMemoryGroupRepository,
} from "../src/gateway/repositories.js";

test("connection failure retries the next upstream", async () => {
  let calls = 0;
  const fixture = createFixture(async () => {
    calls += 1;
    if (calls === 1) throw new TypeError("fetch failed");
    return Response.json(completion("backup"));
  });

  const result = await fixture.router.route(chatRequest());

  assert.equal(result.statusCode, 200);
  assert.equal(result.body.choices[0].message.content, "backup");
  const attempts = await fixture.attempts.list({ requestId: result.requestId });
  assert.equal(attempts.length, 2);
  assert.ok(attempts.some((attempt) => attempt.errorCategory === "CONNECTION_ERROR"));
});

test("total timeout stops before trying another upstream", async () => {
  const fixture = createFixture(
    (_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
    }),
    { totalTimeoutMs: 20, upstreamTimeoutMs: 1_000 },
  );

  const result = await fixture.router.route(chatRequest());

  assert.equal(result.statusCode, 504);
  const attempts = await fixture.attempts.list({ requestId: result.requestId });
  assert.equal(attempts.length, 1);
  assert.equal(attempts[0].errorCategory, "TIMEOUT");
});

function createFixture(fetchImpl, options = {}) {
  const members = [1, 2].map((number) => ({
    id: `member-${number}`,
    priority: number,
    enabled: true,
    model: `real-model-${number}`,
    upstream: {
      id: `upstream-${number}`,
      name: `upstream-${number}`,
      baseUrl: `https://upstream-${number}.example/v1`,
      apiKey: `secret-${number}`,
      enabled: true,
    },
  }));
  const attempts = new InMemoryAttemptRepository();
  return {
    attempts,
    router: new GatewayRouter({
      groupRepository: new InMemoryGroupRepository([{
        id: "group-1",
        routeKey: "demo-route",
        enabled: true,
        members,
      }]),
      attemptRepository: attempts,
      fetchImpl,
      requestIdFactory: () => "edge-request-id",
      maxAttempts: 3,
      upstreamTimeoutMs: options.upstreamTimeoutMs ?? 200,
      totalTimeoutMs: options.totalTimeoutMs ?? 1_000,
    }),
  };
}

function chatRequest() {
  return {
    model: "demo-route",
    messages: [{ role: "user", content: "hello" }],
    stream: false,
  };
}

function completion(content) {
  return {
    id: "chatcmpl-test",
    object: "chat.completion",
    choices: [{ index: 0, message: { role: "assistant", content } }],
  };
}
