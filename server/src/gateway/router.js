import { randomUUID } from "node:crypto";

const RETRYABLE_STATUS_CODES = new Set([408, 429]);
const NON_RETRYABLE_STATUS_CODES = new Set([400, 422]);

export class GatewayRouter {
  constructor({
    groupRepository,
    attemptRepository,
    fetchImpl = globalThis.fetch,
    requestIdFactory = randomUUID,
    maxAttempts = 3,
    upstreamTimeoutMs = 10_000,
    totalTimeoutMs = 25_000,
  }) {
    if (!groupRepository) throw new Error("groupRepository is required");
    if (!attemptRepository) throw new Error("attemptRepository is required");
    if (typeof fetchImpl !== "function") throw new Error("fetchImpl is required");

    this.groupRepository = groupRepository;
    this.attemptRepository = attemptRepository;
    this.fetchImpl = fetchImpl;
    this.requestIdFactory = requestIdFactory;
    this.maxAttempts = Math.max(1, maxAttempts);
    this.upstreamTimeoutMs = Math.max(1, upstreamTimeoutMs);
    this.totalTimeoutMs = Math.max(1, totalTimeoutMs);
  }

  async route(body) {
    const requestId = this.requestIdFactory();
    const validationError = validateRequest(body);
    if (validationError) {
      return gatewayError({
        requestId,
        statusCode: 400,
        code: validationError.code,
        message: validationError.message,
      });
    }

    let group;
    try {
      group = await this.groupRepository.findEnabledGroupByRouteKey(body.model);
    } catch {
      return gatewayError({
        requestId,
        statusCode: 500,
        code: "group_repository_error",
        message: "无法读取 API 分组配置。",
      });
    }

    if (!group) {
      return gatewayError({
        requestId,
        statusCode: 404,
        code: "route_group_not_found",
        message: `未找到已启用的 API 分组：${body.model}`,
      });
    }

    const candidates = buildCandidates(group).slice(0, this.maxAttempts);
    if (candidates.length === 0) {
      return gatewayError({
        requestId,
        statusCode: 503,
        code: "no_available_upstream",
        message: "该 API 分组没有可用的上游。",
      });
    }

    const deadline = Date.now() + this.totalTimeoutMs;
    let lastFailure = null;

    for (let index = 0; index < candidates.length; index += 1) {
      const member = candidates[index];
      const remainingMs = deadline - Date.now();
      if (remainingMs <= 0) {
        lastFailure = {
          category: "TOTAL_TIMEOUT",
          message: "网关请求超过总超时时间。",
        };
        break;
      }

      const result = await this.#callCandidate({
        requestId,
        group,
        member,
        attemptNumber: index + 1,
        body,
        timeoutMs: Math.min(this.upstreamTimeoutMs, remainingMs),
      });

      if (result.kind === "success") {
        return {
          requestId,
          statusCode: result.statusCode,
          body: result.body,
          headers: responseHeaders(requestId, member.upstream.name),
        };
      }

      lastFailure = result;
      if (!result.retryable) {
        return {
          requestId,
          statusCode: result.statusCode,
          body: result.body ?? openAiError(result.message, result.category),
          headers: responseHeaders(requestId, member.upstream.name),
        };
      }
    }

    const timedOut = lastFailure?.category === "TIMEOUT"
      || lastFailure?.category === "TOTAL_TIMEOUT";
    return gatewayError({
      requestId,
      statusCode: timedOut ? 504 : 502,
      code: lastFailure?.category ?? "all_upstreams_failed",
      message: lastFailure?.message ?? "所有候选上游均调用失败。",
    });
  }

  async #callCandidate({
    requestId,
    group,
    member,
    attemptNumber,
    body,
    timeoutMs,
  }) {
    const upstream = member.upstream;
    const startedAt = Date.now();
    const baseAttempt = {
      requestId,
      attemptNumber,
      groupId: group.id,
      groupRouteKey: group.routeKey,
      upstreamId: upstream.id,
      upstreamName: upstream.name,
      model: member.model || upstream.defaultModel,
      occurredAt: new Date().toISOString(),
    };

    if (!upstream.baseUrl || !upstream.apiKey || !baseAttempt.model) {
      const failure = {
        kind: "failure",
        retryable: true,
        statusCode: 502,
        category: "CONFIG_ERROR",
        message: `上游 ${upstream.name} 配置不完整。`,
      };
      await this.#record(baseAttempt, failure, startedAt);
      return failure;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await this.fetchImpl(chatCompletionsUrl(upstream.baseUrl), {
        method: "POST",
        headers: {
          authorization: `Bearer ${upstream.apiKey}`,
          "content-type": "application/json",
          accept: "application/json",
          "x-request-id": requestId,
        },
        body: JSON.stringify({
          ...body,
          model: baseAttempt.model,
          stream: false,
        }),
        signal: controller.signal,
      });

      const parsed = await readJson(response);
      if (response.ok && parsed.ok) {
        const success = {
          kind: "success",
          retryable: false,
          statusCode: response.status,
          body: parsed.value,
        };
        await this.#record(baseAttempt, success, startedAt);
        return success;
      }

      if (response.ok && !parsed.ok) {
        const failure = {
          kind: "failure",
          retryable: true,
          statusCode: 502,
          category: "INVALID_UPSTREAM_RESPONSE",
          message: `上游 ${upstream.name} 返回了无效 JSON。`,
        };
        await this.#record(baseAttempt, failure, startedAt);
        return failure;
      }

      const classified = classifyHttpFailure(response.status, upstream.name);
      const failure = {
        kind: "failure",
        ...classified,
        body: parsed.ok ? parsed.value : undefined,
      };
      await this.#record(baseAttempt, failure, startedAt);
      return failure;
    } catch (error) {
      const timedOut = controller.signal.aborted;
      const failure = {
        kind: "failure",
        retryable: true,
        statusCode: timedOut ? 504 : 502,
        category: timedOut ? "TIMEOUT" : "CONNECTION_ERROR",
        message: timedOut
          ? `上游 ${upstream.name} 请求超时。`
          : `无法连接上游 ${upstream.name}。`,
      };
      await this.#record(baseAttempt, failure, startedAt);
      return failure;
    } finally {
      clearTimeout(timer);
    }
  }

  async #record(baseAttempt, result, startedAt) {
    await this.attemptRepository.record({
      ...baseAttempt,
      status: result.kind === "success" ? "SUCCESS" : "FAILED",
      httpStatus: result.statusCode,
      errorCategory: result.kind === "success" ? null : result.category,
      latencyMs: Math.max(0, Date.now() - startedAt),
    });
  }
}

export function buildCandidates(group) {
  return (group.members ?? [])
    .filter(
      (member) => member.enabled !== false && member.upstream?.enabled !== false,
    )
    .sort((left, right) => {
      const priorityDifference = Number(left.priority ?? 0) - Number(right.priority ?? 0);
      if (priorityDifference !== 0) return priorityDifference;
      return String(left.id ?? "").localeCompare(String(right.id ?? ""));
    });
}

function validateRequest(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { code: "invalid_request", message: "请求体必须是 JSON 对象。" };
  }
  if (body.stream === true) {
    return { code: "stream_not_supported", message: "初版暂不支持流式请求，请设置 stream=false。" };
  }
  if (typeof body.model !== "string" || body.model.trim() === "") {
    return { code: "model_required", message: "model 必须填写 API 分组的 routeKey。" };
  }
  if (!Array.isArray(body.messages) || body.messages.length === 0) {
    return { code: "messages_required", message: "messages 至少包含一条消息。" };
  }
  return null;
}

function classifyHttpFailure(statusCode, upstreamName) {
  if (RETRYABLE_STATUS_CODES.has(statusCode) || statusCode >= 500) {
    return {
      retryable: true,
      statusCode,
      category: statusCode === 429 ? "HTTP_429" : `HTTP_${statusCode}`,
      message: `上游 ${upstreamName} 返回 ${statusCode}，将尝试下一上游。`,
    };
  }

  const category = NON_RETRYABLE_STATUS_CODES.has(statusCode)
    ? `HTTP_${statusCode}`
    : "UPSTREAM_4XX";
  return {
    retryable: false,
    statusCode,
    category,
    message: `上游 ${upstreamName} 返回不可重试的 ${statusCode}。`,
  };
}

async function readJson(response) {
  const text = await response.text();
  if (!text) return { ok: true, value: {} };
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch {
    return { ok: false, value: null };
  }
}

function chatCompletionsUrl(baseUrl) {
  return `${String(baseUrl).replace(/\/+$/, "")}/chat/completions`;
}

function responseHeaders(requestId, upstreamName) {
  return {
    "x-request-id": requestId,
    "x-upstream": upstreamName,
  };
}

function gatewayError({ requestId, statusCode, code, message }) {
  return {
    requestId,
    statusCode,
    body: openAiError(message, code),
    headers: { "x-request-id": requestId },
  };
}

function openAiError(message, code) {
  return {
    error: {
      message,
      type: "gateway_error",
      code,
    },
  };
}
