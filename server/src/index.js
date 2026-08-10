import path from "node:path";
import { fileURLToPath } from "node:url";
import { createGatewayHttpServer } from "./http/app.js";
import { GatewayRouter } from "./gateway/router.js";
import {
  InMemoryAttemptRepository,
  JsonFileGroupRepository,
} from "./gateway/repositories.js";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const configPath = process.env.GATEWAY_CONFIG_PATH
  ?? path.resolve(currentDirectory, "../config/gateway.local.json");
const host = process.env.GATEWAY_HOST ?? "127.0.0.1";
const port = Number(process.env.GATEWAY_PORT ?? 8787);

const groupRepository = new JsonFileGroupRepository(configPath);
const attemptRepository = new InMemoryAttemptRepository();
const router = new GatewayRouter({
  groupRepository,
  attemptRepository,
  maxAttempts: Number(process.env.GATEWAY_MAX_ATTEMPTS ?? 3),
  upstreamTimeoutMs: Number(process.env.GATEWAY_UPSTREAM_TIMEOUT_MS ?? 10_000),
  totalTimeoutMs: Number(process.env.GATEWAY_TOTAL_TIMEOUT_MS ?? 25_000),
});

const server = createGatewayHttpServer({ router, attemptRepository });
server.listen(port, host, () => {
  console.log(`Personal Gateway Plus listening at http://${host}:${port}`);
  console.log(`Gateway config: ${configPath}`);
});
