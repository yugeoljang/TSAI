import assert from "node:assert/strict";
import { once } from "node:events";
import { after, before, test } from "node:test";
import { GatewayRouter } from "../src/gateway/router.js";
import {
  InMemoryAttemptRepository,
  InMemoryGroupRepository,
} from "../src/gateway/repositories.js";
import { createGatewayHttpServer } from "../src/http/app.js";

let server;
let baseUrl;

before(async () => {
  const attempts = new InMemoryAttemptRepository();
  const router = new GatewayRouter({
    groupRepository: new InMemoryGroupRepository([]),
    attemptRepository: attempts,
    requestIdFactory: () => "http-request-id",
  });
  server = createGatewayHttpServer({ router, attemptRepository: attempts });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

after(() => new Promise((resolve) => server.close(resolve)));

test("health endpoint is available", async () => {
  const response = await fetch(`${baseUrl}/health`);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: "ok" });
});

test("chat endpoint returns OpenAI-compatible error and request id", async () => {
  const response = await fetch(`${baseUrl}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model: "missing-route",
      messages: [{ role: "user", content: "hello" }],
    }),
  });

  assert.equal(response.status, 404);
  assert.equal(response.headers.get("x-request-id"), "http-request-id");
  const body = await response.json();
  assert.equal(body.error.type, "gateway_error");
  assert.equal(body.error.code, "route_group_not_found");
});
