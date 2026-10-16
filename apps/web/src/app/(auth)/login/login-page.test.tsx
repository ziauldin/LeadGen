import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/server";
import { renderWithClient } from "@/test/render";
import { router } from "@/test/setup";
import { AuthProvider } from "@/hooks/use-auth";
import LoginPage from "./page";

const api = (path: string) => `http://localhost:3000/api${path}`;

function renderLogin() {
  return renderWithClient(
    <AuthProvider>
      <LoginPage />
    </AuthProvider>,
  );
}

describe("login with two-factor authentication", () => {
  it("asks for a code after the password and signs in with it", async () => {
    const user = userEvent.setup();
    let submittedCode = "";
    server.use(
      http.post(api("/auth/refresh"), () => new HttpResponse(null, { status: 401 })),
      http.post(api("/auth/login"), () =>
        HttpResponse.json({ mfa_required: true, mfa_token: "mfa-token-123", access_token: null }),
      ),
      http.post(api("/auth/login/2fa"), async ({ request }) => {
        const body = (await request.json()) as { mfa_token: string; code: string };
        submittedCode = body.code;
        expect(body.mfa_token).toBe("mfa-token-123");
        return HttpResponse.json({ access_token: "access-1", expires_in: 900 });
      }),
      http.get(api("/auth/me"), () =>
        HttpResponse.json({
          id: 1,
          name: "Sam",
          email: "sam@acme.co.uk",
          role: "operator",
          email_verified_at: null,
          mfa_enabled: true,
          created_at: "2026-01-01T00:00:00Z",
        }),
      ),
    );
    renderLogin();

    await user.type(await screen.findByLabelText("Email"), "sam@acme.co.uk");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    const codeInput = await screen.findByLabelText("Authentication code");
    await user.type(codeInput, "123456");
    await user.click(screen.getByRole("button", { name: "Verify and sign in" }));

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/dashboard"));
    expect(submittedCode).toBe("123456");
  });

  it("offers recovery codes and shows wrong-code errors", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(api("/auth/refresh"), () => new HttpResponse(null, { status: 401 })),
      http.post(api("/auth/login"), () =>
        HttpResponse.json({ mfa_required: true, mfa_token: "mfa-token-123" }),
      ),
      http.post(api("/auth/login/2fa"), () =>
        HttpResponse.json({ detail: "That code isn't right." }, { status: 401 }),
      ),
    );
    renderLogin();
    await user.type(await screen.findByLabelText("Email"), "sam@acme.co.uk");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await user.click(await screen.findByRole("button", { name: "Use a recovery code instead" }));
    await user.type(screen.getByLabelText("Recovery code"), "abcd-ef01-2345");
    await user.click(screen.getByRole("button", { name: "Verify and sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That code isn't right.");
  });
});
