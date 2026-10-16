import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LEGAL_DOCUMENTS, legalDocument } from "@/content/legal";

export function generateStaticParams() {
  return LEGAL_DOCUMENTS.map((doc) => ({ slug: doc.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const doc = legalDocument((await params).slug);
  if (!doc) return {};
  return { title: `${doc.title} · LeadsGen`, description: doc.summary, alternates: { canonical: `/legal/${doc.slug}` } };
}

export default async function LegalPage({ params }: { params: Promise<{ slug: string }> }) {
  const doc = legalDocument((await params).slug);
  if (!doc) notFound();
  return (
    <article className="mx-auto max-w-3xl">
      <h1 className="text-[32px] font-bold">{doc.title}</h1>
      <p className="mt-2 text-[14px] text-[var(--on-surface-variant)]">
        Last updated {new Date(doc.updated).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
      </p>
      <p className="mt-6 text-[16px] leading-7">{doc.summary}</p>
      {doc.sections.map((section) => (
        <section key={section.heading} className="mt-8">
          <h2 className="text-[19px] font-semibold">{section.heading}</h2>
          {section.body.map((block, index) =>
            Array.isArray(block) ? (
              <ul key={index} className="mt-3 list-disc space-y-1.5 pl-6 text-[15px] leading-7">
                {block.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p key={index} className="mt-3 text-[15px] leading-7">
                {block}
              </p>
            ),
          )}
        </section>
      ))}
    </article>
  );
}
