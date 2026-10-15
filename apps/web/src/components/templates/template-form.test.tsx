import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EMPTY_TEMPLATE, TemplateForm } from "@/components/templates/template-form";
import {
  containsVariable,
  findVariables,
  renderSample,
  templateSchema,
} from "@/components/templates/template-validation";

const valid = {
  name: "Clinic intro",
  description: "",
  subject: "Hello {{company}}",
  body: "Hi {{first_name}},\n\nOpt out: {{unsubscribe_link}}",
};

function setup(overrides: Partial<React.ComponentProps<typeof TemplateForm>> = {}) {
  const onSubmit = vi.fn();
  const onCancel = vi.fn();
  render(
    <TemplateForm
      defaultValues={valid}
      onSubmit={onSubmit}
      onCancel={onCancel}
      {...overrides}
    />,
  );
  return { onSubmit, onCancel };
}

describe("template validation", () => {
  it("accepts a valid template", () => {
    expect(templateSchema().safeParse(valid).success).toBe(true);
  });

  it("rejects unknown variables and a missing opt-out link", () => {
    const result = templateSchema().safeParse({
      ...valid,
      subject: "Hi {{nickname}}",
      body: "Hello {{ first_name }} from {{ sender_compnay }}",
    });
    expect(result.success).toBe(false);
    const messages = result.error!.issues.map((issue) => `${String(issue.path[0])}: ${issue.message}`);
    expect(messages).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/^subject: \{\{nickname\}\} isn't a variable/),
        expect.stringMatching(/^body: \{\{sender_compnay\}\} isn't a variable/),
        expect.stringMatching(/^body: Include \{\{unsubscribe_link\}\}/),
      ]),
    );
  });

  it("finds variables with spaces like the API does", () => {
    expect(findVariables("{{ first_name }} {{company}} {{first_name}}")).toEqual([
      "first_name",
      "company",
    ]);
    expect(containsVariable("x {{ unsubscribe_link }}", "unsubscribe_link")).toBe(true);
    expect(renderSample("Hi {{first_name}} {{unknown}}")).toBe("Hi Alex {{unknown}}");
  });
});

describe("TemplateForm", () => {
  it("submits valid values", async () => {
    const user = userEvent.setup();
    const { onSubmit } = setup();
    await user.click(screen.getByRole("button", { name: "Save template" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toEqual(valid);
  });

  it("blocks submit and explains what's wrong", async () => {
    const user = userEvent.setup();
    const { onSubmit } = setup({ defaultValues: { ...EMPTY_TEMPLATE, body: "Hello {{nickname}}" } });
    await user.click(screen.getByRole("button", { name: "Save template" }));

    expect(await screen.findByText("Give the template a name.")).toBeInTheDocument();
    expect(screen.getByText("Add a subject line.")).toBeInTheDocument();
    expect(screen.getByText(/\{\{nickname\}\} isn't a variable/)).toBeInTheDocument();
    expect(screen.getByLabelText("Body")).toHaveAttribute("aria-invalid", "true");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("requires the unsubscribe link in the body", async () => {
    const user = userEvent.setup();
    const { onSubmit } = setup({ defaultValues: { ...valid, body: "Hi {{first_name}}" } });
    await user.click(screen.getByRole("button", { name: "Save template" }));
    expect(
      await screen.findByText(/Include \{\{unsubscribe_link\}\} in the body/),
    ).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("inserts a variable at the cursor and clears the error", async () => {
    const user = userEvent.setup();
    const { onSubmit } = setup({ defaultValues: { ...valid, body: "Hi ," } });
    const body = screen.getByLabelText("Body") as HTMLTextAreaElement;
    await user.click(screen.getByRole("button", { name: "Save template" }));
    expect(await screen.findByText(/Include \{\{unsubscribe_link\}\}/)).toBeInTheDocument();

    body.focus();
    body.setSelectionRange(3, 3);
    await user.click(screen.getByRole("button", { name: "Insert first_name" }));
    expect(body.value).toBe("Hi {{first_name}},");

    body.setSelectionRange(body.value.length, body.value.length);
    await user.click(screen.getByRole("button", { name: "Insert unsubscribe_link" }));
    expect(body.value).toBe("Hi {{first_name}},{{unsubscribe_link}}");
    await waitFor(() =>
      expect(screen.queryByText(/Include \{\{unsubscribe_link\}\}/)).not.toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "Save template" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
  });

  it("shows the API's error message", () => {
    setup({ serverError: "Unknown variables: nickname" });
    expect(screen.getByRole("alert")).toHaveTextContent("Unknown variables: nickname");
  });
});
