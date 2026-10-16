import { defineCloudflareConfig } from "@opennextjs/cloudflare";

export default defineCloudflareConfig({
  // Revalidation runs synchronously in the same request rather than via a
  // background Worker invocation. Simpler to operate; fine for most apps.
  // Switch to the default (self-reference) once you add the R2 cache bucket.
  queue: "direct",
});
