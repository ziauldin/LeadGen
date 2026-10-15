import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import {
  SuppressionAddForm,
  validateSuppression,
} from "@/components/settings/suppression-add-form";
import { renderWithClient } from "@/test/render";
import { server } from "@/test/server";

const url = (path: string) => `http://localhost:3000/api${path}`;

async function chooseType(user: ReturnType<typeof userEvent.setup>, label: string) {
  await user.click(screen.getByRole("combobox", { name: "Type" }));
  await user.click(await screen.findByRole("option", { name: label }));
}

describe("validateSuppression", () => {
  it("checks the value against the chosen type", () => {
    expect(validateSuppression("email", "")).toMatch(/Enter an email address/);
    expect(validateSuppression("email", "acme.com")).toMatch(/looks like a domain/);
    expect(validateSuppression("email", "jane@acme.com")).toBeNull();
    expect(validateSuppression("domain", "jane@acme.com")).toMatch(/just the domain/);
    expect(validateSuppression("domain", "not a domain")).toMatch(/valid domain/);
    expect(validateSuppression("domain", "Gmail.com")).toMatch(/shared email provider/);
    expect(validateSuppression("domain", "@acme.co.uk")).toBeNull();
  });
});

describe("SuppressionAddForm", () => {
  it("blocks free-mail domains without calling the API", async () => {
    const user = userEvent.setup();
    let calls = 0;
    server.use(
      http.post(url("/suppressions"), () => {
        calls += 1;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderWithClient(<SuppressionAddForm />);

    await chooseType(user, "Whole domain");
    await user.type(screen.getByLabelText("Domain"), "gmail.com");
    await user.click(screen.getByRole("button", { name: /Add to suppression list/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/can't be blocked as a whole/);
    expect(screen.getByLabelText("Domain")).toHaveAttribute("aria-invalid", "true");
    expect(calls).toBe(0);
  });

  it("asks for an address when a domain is typed as an email", async () => {
    const user = userEvent.setup();
    renderWithClient(<SuppressionAddForm />);
    await user.type(screen.getByLabelText("Email address"), "acme.com");
    await user.click(screen.getByRole("button", { name: /Add to suppression list/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/looks like a domain/);
  });

  it("sends a domain suppression and clears the form", async () => {
    const user = userEvent.setup();
    let body: unknown;
    server.use(
      http.post(url("/suppressions"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          {
            id: 1,
            email: null,
            domain: "acme.com",
            reason: "Competitor",
            source: "manual",
            created_at: "2026-10-01T10:00:00Z",
          },
          { status: 201 },
        );
      }),
    );
    renderWithClient(<SuppressionAddForm />);

    await chooseType(user, "Whole domain");
    await user.type(screen.getByLabelText("Domain"), " @Acme.com ");
    await user.type(screen.getByLabelText(/Reason/), "Competitor");
    await user.click(screen.getByRole("button", { name: /Add to suppression list/ }));

    await waitFor(() =>
      expect(body).toEqual({ domain: "acme.com", reason: "Competitor", source: "manual" }),
    );
    await waitFor(() => expect(screen.getByLabelText("Domain")).toHaveValue(""));
  });

  it("shows the API's reason when it refuses", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(url("/suppressions"), () =>
        HttpResponse.json({ detail: "Suppression already exists" }, { status: 409 }),
      ),
    );
    renderWithClient(<SuppressionAddForm />);
    await user.type(screen.getByLabelText("Email address"), "jane@acme.com");
    await user.click(screen.getByRole("button", { name: /Add to suppression list/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Suppression already exists");
  });
});
