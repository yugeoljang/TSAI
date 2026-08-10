import assert from "node:assert/strict";
import { createServer } from "node:http";
import { afterEach, test } from "node:test";
import { GatewayRouter } from "../src/gateway/router.js";
import {
  InMemoryAttemptRepository,
  InMemoryGroupRepository,
} from "../src/gateway/repositories.js";

const openServers = [];

afterEach(async () => {
  await Promise.all(openServers.splice(0).map((server) => closeServer(server)));
});

test("first upstream succeeds without calling the backup", async () => {
  const primary = await mockUpstream([{ status: 200, body: completion("primary") }]);
  const backup = await mockUpstream([{ status: 200, body: completion("backup") }]);
  const fixture = createFixture([primary, backup]);

  const result = await fixture.router.route(chatRequest());

  assert.equal(result.statusCode, 200);
  assert.equal(result.body.choices[0].message.content, "primary");
  assert.equal(result.headers["x-gateway-upstream"], "upstream-1");
  assert.equal(primary.hits, 1);
  assert.equal(backup.hits, 0);
  assert.equal((await fixture.attempts.list()).length, 1);
});

test("500 retries the next upstream in priority order", async () => {
  const primary = await mockUpstream([{ status: 500, body: { error: { message: "down" } } }]);
  const backup = await mockUpstream([{ status: 200, body: completion("backup") }]);
  const fixture = createFixture([primary, backup]);

  const result = await fixture.router.route(chatRequest());
  const attempts = await fixture.attempts.list({ requestId: result.requestId });

  assert.equal(result.statusCode, 200);
  assert.equal(result.body.choices[0].message.content, "backup");
  assert.equal(result.headers["x-gateway-upstream"], "upstream-2");
  assert.equal(primary.hits, 1);
  assert.equal(backup.hits, 1);
  assert.deepEqual(attempts.map((item) => item.errorCategory).reverse(), ["HTTP_500", null]);
});

test("429 retries the next upstream", async () => {
  const primary = await mockUpstream([{ status: 429, body: { error: { message: "limited" } } }]);
  const backup = await mockUpstream([{ status: 200, body: completion("backup") }]);
  const fixture = createFixture([primary, backup]);

  const result = await fixture.router.route(chatRequest());

  assert.equal(result.statusCode, 200);
  assert.equal(backup.hits, 1);
  const attempts = await fixture.attempts.list({ requestId: result.requestId });
  assert.equal(attempts.at(-1).errorCategory, "HTTP_429");
});

test("upstream timeout retries the next upstream", async () => {
  const primary = await mockUpstream([{ status: 200, delayMs: 150, body: completion("late") }]);
  const backup = await mockUpstream([{ status: 200, body: completion("backup") }]);
  const fixture = createFixture([primary, backup], { upstreamTimeoutMs: 30 });

  const result = await fixture.router.route(chatRequest());

  assert.equal(result.statusCode, 200);
  assert.equal(result.body.choices[0].message.content, "backup");
  const attempts = await fixture.attempts.list({ requestId: result.requestId });
  assert.ok(attempts.some((attempt) => attempt.errorCategory === "TIMEOUT"));
});

test("400 does not retry the backup", async () => {
  const primaryBody = { error: { message: "bad request", type: "invalid_request_error" } };
  const primary = await mockUpstream([{ status: 400, body: primaryBody }]);
  const backup = await mockUpstream([{ status: 200, body: completion("backup") }]);
  const fixture = createFixture([primary, backup]);

  const result = await fixture.router.route(chatRequest());

  assert.equal(result.statusCode, 400);
  assert.deepEqual(result.body, primaryBody);
  assert.equal(primary.hits, 1);
  assert.equal(backup.hits, 0);
});

test("maximum attempts limits routing to three upstreams", async () => {
  const upstreams = await Promise.all(
    [1, 2, 3, 4].map(() => mockUpstream([{ status: 500, body: { error: {} } }])),
  );
  const fixture = createFixture(upstreams, { maxAttempts: 3 });

  const result = await fixture.router.route(chatRequest());

  assert.equal(result.statusCode, 502);
  assert.deepEqual(upstreams.map((upstream) => upstream.hits), [1, 1, 1, 0]);
  const attempts = await fixture.attempts.list({ requestId: result.requestId });
  assert.equal(attempts.length, 3);
});

test("stream=true is rejected before any upstream call", async () => {
  const primary = await mockUpstream([{ status: 200, body: completion("primary") }]);
  const fixture = createFixture([primary]);

  const result = await fixture.router.route({ ...chatRequest(), stream: true });

  assert.equal(result.statusCode, 400);
  assert.equal(result.body.error.code, "stream_not_supported");
  assert.equal(primary.hits, 0);
});

test("route key selects the group and member model replaces the virtual model", async () => {
  let receivedBody;
  const primary = await mockUpstream([{
    status: 200,
    body: completion("mapped"),
    onRequest: (body) => { receivedBody = body; },
  }]);
  const fixture = createFixture([primary]);

  await fixture.router.route(chatRequest());

  assert.equal(receivedBody.model, "real-model-1");
  assert.equal(receivedBody.stream, false);
});

function createFixture(upstreams, options = {}) {
  const members = upstreams.map((upstream, index) => ({
    id: `member-${index + 1}`,
    priority: index + 1,
    enabled: true,
    model: `real-model-${index + 1}`,
    upstream: {
      id: `upstream-${index + 1}`,
      name: `upstream-${index + 1}`,
      baseUrl: `${upstream.url}/v1`,
      apiKey: `test-key-${index + 1}`,
      enabled: true,
    },
  }));
  const groups = [{
    id: "group-1",
    routeKey: "demo-route",
    enabled: true,
    members,
  }];
  const attempts = new InMemoryAttemptRepository();
  return {
    attempts,
    router: new GatewayRouter({
      groupRepository: new InMemoryGroupRepository(groups),
      attemptRepository: attempts,
      upstreamTimeoutMs: options.upstreamTimeoutMs ?? 500,
      totalTimeoutMs: options.totalTimeoutMs ?? 2_000,
      maxAttempts: options.maxAttempts ?? 3,
      requestIdFactory: () => "request-test-id",
    }),
  };
}

async function mockUpstream(sequence) {
  let hits = 0;
  const server = createServer(async (request, response) => {
    hits += 1;
    const body = await readRequestBody(request);
    const behavior = sequence[Math.min(hits - 1, sequence.length - 1)];
    behavior.onRequest?.(body);
    if (behavior.delayMs) {
      await new Promise((resolve) => setTimeout(resolve, behavior.delayMs));
    }
    if (response.destroyed) return;
    response.statusCode = behavior.status;
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify(behavior.body));
  });
  await listen(server);
  openServers.push(server);
  const address = server.address();
  return {
    get hits() { return hits; },
    url: `http://127.0.0.1:${address.port}`,
  };
}

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
}

function closeServer(server) {
  return new Promise((resolve) => server.close(resolve));
}

async function readRequestBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
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
