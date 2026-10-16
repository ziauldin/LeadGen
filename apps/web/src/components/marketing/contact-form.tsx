"use client";

import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Captcha } from "@/components/auth/captcha";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, getErrorMessage } from "@/lib/api/client";

const TOPICS: Record<string, string> = {
  sales: "Sales and demos",
  support: "Help with my account",
  privacy: "Privacy or data request",
  other: "Something else",
};

export function ContactForm() {
  const [topic, setTopic] = useState("sales");
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const [status, setStatus] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setStatus("sending");
    setError(null);
    try {
      await apiFetch("/contact", {
        method: "POST",
        skipAuthRetry: true,
        body: JSON.stringify({
          name: form.get("name"),
          email: form.get("email"),
          company: form.get("company") || null,
          topic,
          message: form.get("message"),
          website: form.get("website") || null,
          captcha_token: captchaToken,
        }),
      });
      setStatus("sent");
    } catch (err) {
      setError(getErrorMessage(err));
      setStatus("idle");
      setCaptchaReset((n) => n + 1);
    }
  }

  if (status === "sent") {
    return (
      <p role="status" className="flex items-start gap-2 rounded-lg bg-[var(--primary-fixed)] p-4 text-[15px] text-[var(--on-primary-fixed)]">
        <CheckCircle2 className="mt-0.5 size-5 shrink-0" aria-hidden />
        Thanks, your message is on its way. We usually reply within one working day.
      </p>
    );
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <label htmlFor="contact-name" className="text-[13px] font-medium">Your name</label>
          <Input id="contact-name" name="name" required maxLength={120} autoComplete="name" className="bg-white" />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor="contact-email" className="text-[13px] font-medium">Work email</label>
          <Input id="contact-email" name="email" type="email" required autoComplete="email" className="bg-white" />
        </div>
        <div className="grid gap-1.5">
          <label htmlFor="contact-company" className="text-[13px] font-medium">
            Company <span className="font-normal text-muted-foreground">(optional)</span>
          </label>
          <Input id="contact-company" name="company" maxLength={200} autoComplete="organization" className="bg-white" />
        </div>
        <div className="grid gap-1.5">
          <label id="contact-topic-label" className="text-[13px] font-medium">Topic</label>
          <Select value={topic} items={TOPICS} onValueChange={(value) => setTopic(String(value ?? "sales"))}>
            <SelectTrigger className="w-full bg-white" aria-labelledby="contact-topic-label">
              <SelectValue />
            </SelectTrigger>
            <SelectContent alignItemWithTrigger={false}>
              {Object.entries(TOPICS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid gap-1.5">
        <label htmlFor="contact-message" className="text-[13px] font-medium">How can we help?</label>
        <Textarea id="contact-message" name="message" required minLength={10} maxLength={5000} rows={6} className="bg-white" />
      </div>
      {/* Hidden from people; bots tend to fill it in. */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-0 overflow-hidden">
        <label htmlFor="contact-website">Website</label>
        <input id="contact-website" name="website" tabIndex={-1} autoComplete="off" />
      </div>
      <Captcha onToken={setCaptchaToken} resetKey={captchaReset} />
      {error ? (
        <p role="alert" className="rounded-md bg-[var(--error-container)] px-3 py-2 text-[13px] text-[var(--on-error-container)]">
          {error}
        </p>
      ) : null}
      <div>
        <Button type="submit" disabled={status === "sending"}>
          {status === "sending" ? "Sending…" : "Send message"}
        </Button>
      </div>
    </form>
  );
}
