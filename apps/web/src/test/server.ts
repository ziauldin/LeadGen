import { setupServer } from "msw/node";

/** Mock API for component tests. Tests add handlers with `server.use(...)`. */
export const server = setupServer();
