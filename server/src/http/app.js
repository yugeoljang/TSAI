import { createServer } from "node:http";

const MAX_BODY_BYTES = 1024 * 1024;

export function createGatewayHttpServer({ router, attemptRepository }) {
  return createServer(async (request, response) => {
    setCorsHeaders(response);

    if (request.method === "OPTIONS") {
      response.writeHead(204).end();
      return;
    }

    const url = new URL(request.url, "http://localhost");

    if (request.method === "GET" && url.pathname === "/health") {
      sendJson(response, 200, { status: "ok" });
      return;
    }

    const attemptMatch = url.pathname.match(/^\/api\/admin\/requests\/([^/]+)\/attempts$/);
    if (request.method === "GET" && (url.pathname === "/gateway/route-attempts" || attemptMatch)) {
      const attempts = await attemptRepository.list({
        requestId: attemptMatch?.[1] || url.searchParams.get("requestId") || undefined,
        limit: Number(url.searchParams.get("limit") || 20),
      });
      sendJson(response, 200, { items: attempts });
      return;
    }

    if (request.method === "POST" && url.pathname === "/v1/chat/completions") {
      try {
        const body = await readJsonBody(request);
        const result = await router.route(body);
        for (const [name, value] of Object.entries(result.headers ?? {})) {
          response.setHeader(name, value);
        }
        sendJson(response, result.statusCode, result.body);
      } catch (error) {
        const statusCode = error.code === "BODY_TOO_LARGE" ? 413 : 400;
        sendJson(response, statusCode, {
          error: {
            message: statusCode === 413 ? "请求体超过 1 MiB 限制。" : "请求体不是有效 JSON。",
            type: "gateway_error",
            code: error.code ?? "invalid_json",
          },
        });
      }
      return;
    }

    sendJson(response, 404, {
      error: { message: "接口不存在。", type: "gateway_error", code: "not_found" },
    });
  });
}

async function readJsonBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      const error = new Error("body too large");
      error.code = "BODY_TOO_LARGE";
      throw error;
    }
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function setCorsHeaders(response) {
  response.setHeader("access-control-allow-origin", "http://localhost:5173");
  response.setHeader("access-control-allow-methods", "GET,POST,OPTIONS");
  response.setHeader("access-control-allow-headers", "content-type,authorization,x-request-id");
  response.setHeader("access-control-expose-headers", "x-request-id,x-upstream");
}

function sendJson(response, statusCode, body) {
  response.statusCode = statusCode;
  response.setHeader("content-type", "application/json; charset=utf-8");
  response.end(JSON.stringify(body));
}
