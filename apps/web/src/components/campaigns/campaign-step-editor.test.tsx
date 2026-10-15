import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormProvider, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { describe, expect, it, vi } from "vitest";
import { CampaignStepEditor } from "@/components/campaigns/campaign-step-editor";
import {
  campaignFormSchema,
  defaultCampaignValues,
  stepsToPayload,
  type CampaignFormValues,
} from "@/components/campaigns/campaign-form-schema";
import type { EmailTemplate } from "@/lib/api/types";

const TEMPLATES: EmailTemplate[] = [
  {
    id: "system:intro",
    name: "Introduction",
    description: "A short first email.",
    subject: "Quick question about {{company}}",
    body: "Hi {{first_name}},\n\nOpt out: {{unsubscribe_link}}",
    is_system: true,
    is_archived: false,
  },
  {
    id: "system:follow-up",
    name: "Gentle follow-up",
    description: "",
    subject: "Re: Quick question about {{company}}",
    body: "Following up.\n\nOpt out: {{unsubscribe_link}}",
    is_system: true,
    is_archived: false,
  },
];

function Harness({ onValid }: { onValid: (values: CampaignFormValues) => void }) {
  const form = useForm<CampaignFormValues>({
    resolver: zodResolver(campaignFormSchema),
    defaultValues: { ...defaultCampaignValues(1), name: "Test campaign", timezone: "UTC" },
  });
  return (
    <FormProvider {...form}>
      <form onSubmit={form.handleSubmit(onValid)}>
        <CampaignStepEditor templates={TEMPLATES} />
        <button type="submit">Save</button>
      </form>
    </FormProvider>
  );
}

function setup() {
  const onValid = vi.fn();
  const user = userEvent.setup();
  render(<Harness onValid={onValid} />);
  return { user, onValid };
}

const steps = () => screen.getAllByRole("article", { name: /^Step \d+$/ });
const step = (number: number) => screen.getByRole("article", { name: `Step ${number}` });

describe("CampaignStepEditor", () => {
  it("starts with an intro step and a 3-day follow-up, each with a template preview", () => {
    setup();
    expect(steps()).toHaveLength(2);

    const first = step(1);
    expect(within(first).getByText("Sends immediately once approved.")).toBeInTheDocument();
    expect(within(first).queryByLabelText("Wait before sending")).not.toBeInTheDocument();
    expect(within(first).getByLabelText("Template")).toHaveValue("system:intro");
    expect(within(first).getByLabelText("Preview of Introduction")).toHaveTextContent(
      "Quick question about {{company}}",
    );
    // Threading only makes sense for follow-ups.
    expect(
      within(first).queryByRole("switch", { name: /same thread/i }),
    ).not.toBeInTheDocument();

    const second = step(2);
    expect(within(second).getByLabelText("Wait before sending")).toHaveValue(3);
    expect(within(second).getByLabelText("Template")).toHaveValue("system:follow-up");
    expect(within(second).getByRole("switch", { name: /same thread/i })).toBeChecked();
  });

  it("adds, reorders and removes steps", async () => {
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Add follow-up step" }));
    expect(steps()).toHaveLength(3);

    await user.click(screen.getByRole("button", { name: "Move step 2 up" }));
    expect(within(step(1)).getByLabelText("Template")).toHaveValue("system:follow-up");
    expect(within(step(2)).getByLabelText("Template")).toHaveValue("system:intro");

    await user.click(screen.getByRole("button", { name: "Remove step 3" }));
    await user.click(screen.getByRole("button", { name: "Remove step 2" }));
    expect(steps()).toHaveLength(1);
    // The last step can't be removed.
    expect(screen.getByRole("button", { name: "Remove step 1" })).toBeDisabled();
  });

  it("switching to custom copies the template text into editable fields", async () => {
    const { user } = setup();
    const first = step(1);
    await user.click(within(first).getByRole("radio", { name: "Custom" }));

    expect(within(first).getByLabelText("Subject")).toHaveValue("Quick question about {{company}}");
    expect(within(first).getByLabelText("Body")).toHaveValue(TEMPLATES[0].body);
    expect(within(first).queryByLabelText("Template")).not.toBeInTheDocument();
    expect(within(first).getByText("Opt-out link included")).toBeInTheDocument();
  });

  it("blocks a custom email without an unsubscribe link until one is inserted", async () => {
    const { user, onValid } = setup();
    const first = step(1);
    await user.click(within(first).getByRole("radio", { name: "Custom" }));

    const body = within(first).getByLabelText("Body");
    await user.clear(body);
    await user.type(body, "Hi there, just checking in.");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await within(first).findByText(/must include \{\{unsubscribe_link\}\}/),
    ).toBeInTheDocument();
    expect(onValid).not.toHaveBeenCalled();

    await user.click(body);
    await user.click(within(first).getByRole("button", { name: "Insert unsubscribe_link" }));
    await waitFor(() => expect(body).toHaveValue("Hi there, just checking in.{{unsubscribe_link}}"));
    await waitFor(() =>
      expect(within(first).queryByText(/must include \{\{unsubscribe_link\}\}/)).not.toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onValid).toHaveBeenCalledTimes(1));
    const payload = stepsToPayload(onValid.mock.calls[0][0].steps);
    expect(payload[0]).toMatchObject({
      step_number: 1,
      delay_days: 0,
      template_id: null,
      subject_template: "Quick question about {{company}}",
      body_template: "Hi there, just checking in.{{unsubscribe_link}}",
      thread_with_previous: false,
    });
    expect(payload[1]).toMatchObject({
      step_number: 2,
      delay_days: 3,
      template_id: "system:follow-up",
      subject_template: null,
      body_template: null,
    });
  });

  it("requires a template when the source is a saved template", async () => {
    const { user, onValid } = setup();
    const second = step(2);
    await user.selectOptions(within(second).getByLabelText("Template"), "");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await within(second).findByText("Choose a template", { selector: "p" })).toBeInTheDocument();
    expect(onValid).not.toHaveBeenCalled();
  });

  it("shows AI instructions only when Write with AI is on", async () => {
    const { user } = setup();
    const first = step(1);
    expect(within(first).queryByLabelText(/Instructions for the AI draft/)).not.toBeInTheDocument();
    await user.click(within(first).getByRole("switch", { name: /Write with AI/ }));
    expect(within(first).getByLabelText(/Instructions for the AI draft/)).toBeInTheDocument();
    expect(within(first).getByText(/the template above is used instead/)).toBeInTheDocument();
  });
});
