// Serve the same standalone output used by Docker, against the isolated test API.
import { cp, access } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { join } from "node:path";

const frontend = fileURLToPath(new URL("../frontend/", import.meta.url));
const standalone = join(frontend, ".next", "standalone");
await cp(
  join(frontend, ".next", "static"),
  join(standalone, ".next", "static"),
  {
    recursive: true,
  },
);
try {
  await access(join(frontend, "public"));
  await cp(join(frontend, "public"), join(standalone, "public"), {
    recursive: true,
  });
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
process.env.PORT = "3010";
process.env.HOSTNAME = "127.0.0.1";
await import(pathToFileURL(join(standalone, "server.js")).href);
