import { readFile } from "node:fs/promises";
import path from "node:path";

export class InMemoryGroupRepository {
  constructor(groups = []) {
    this.groups = groups;
  }

  async findEnabledGroupByRouteKey(routeKey) {
    return this.groups.find(
      (group) => group.enabled !== false && group.routeKey === routeKey,
    ) ?? null;
  }
}

export class JsonFileGroupRepository {
  constructor(configPath) {
    this.configPath = path.resolve(configPath);
  }

  async findEnabledGroupByRouteKey(routeKey) {
    const raw = await readFile(this.configPath, "utf8");
    const config = JSON.parse(raw);
    const group = (config.groups ?? []).find(
      (item) => item.enabled !== false && item.routeKey === routeKey,
    );

    if (!group) {
      return null;
    }

    return {
      ...group,
      members: (group.members ?? []).map((member) => ({
        ...member,
        upstream: resolveUpstreamSecret(member.upstream),
      })),
    };
  }
}

function resolveUpstreamSecret(upstream = {}) {
  const apiKey = upstream.apiKeyEnv
    ? process.env[upstream.apiKeyEnv]
    : upstream.apiKey;

  return {
    ...upstream,
    apiKey,
    apiKeyEnv: undefined,
  };
}

export class InMemoryAttemptRepository {
  constructor(limit = 200) {
    this.limit = limit;
    this.attempts = [];
  }

  async record(attempt) {
    this.attempts.push({ ...attempt });
    if (this.attempts.length > this.limit) {
      this.attempts.splice(0, this.attempts.length - this.limit);
    }
  }

  async list({ requestId, limit = 20 } = {}) {
    const filtered = requestId
      ? this.attempts.filter((attempt) => attempt.requestId === requestId)
      : this.attempts;
    return filtered.slice(-Math.max(1, limit)).reverse();
  }
}
