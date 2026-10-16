import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/page-header";
import { TemplateLibrary } from "@/components/templates/template-library";

export const metadata: Metadata = { title: "Templates — LeadsGen" };

export default function TemplatesPage() {
  return (
    <div>
      <PageHeader
        title="Templates"
        description="Reusable emails for campaigns and Email Studio. AI drafts use them as their starting point too."
      />
      <TemplateLibrary />
    </div>
  );
}
