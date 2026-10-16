import type { Metadata } from "next";
import {
  PLATFORM_SUBPROCESSORS,
  WORKSPACE_SUBPROCESSORS,
  type Subprocessor,
} from "@/lib/subprocessors";

export const metadata: Metadata = {
  title: "Subprocessors · LeadsGen",
  description: "Third parties that may process personal data on behalf of LeadsGen and its customers.",
};

function SubprocessorTable({ caption, rows }: { caption: string; rows: Subprocessor[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-lowest)]" tabIndex={0}>
      <table className="w-full min-w-[640px] text-left text-[13px]">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-[var(--surface-container-low)] text-[12px] text-[var(--on-surface-variant)]">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">Subprocessor</th>
            <th scope="col" className="px-4 py-2 font-medium">Purpose</th>
            <th scope="col" className="px-4 py-2 font-medium">Personal data</th>
            <th scope="col" className="px-4 py-2 font-medium">Location</th>
            <th scope="col" className="px-4 py-2 font-medium">Used</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--outline-variant)]">
          {rows.map((row) => (
            <tr key={row.name}>
              <th scope="row" className="px-4 py-3 font-medium">{row.name}</th>
              <td className="px-4 py-3 text-[var(--on-surface-variant)]">{row.purpose}</td>
              <td className="px-4 py-3 text-[var(--on-surface-variant)]">{row.data}</td>
              <td className="px-4 py-3 text-[var(--on-surface-variant)]">{row.location}</td>
              <td className="px-4 py-3 text-[var(--on-surface-variant)]">{row.when}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SubprocessorsPage() {
  return (
    <article className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-[28px] font-semibold">Subprocessors</h1>
        <p className="max-w-2xl text-[14px] text-[var(--on-surface-variant)]">
          LeadsGen uses these third parties to run the service. Customers are the controllers of the
          lead data they hold; we process it on their instructions. We give 30 days&apos; notice before
          adding a platform subprocessor.
        </p>
      </header>
      <section className="space-y-3">
        <h2 className="text-[18px] font-semibold">Platform</h2>
        <SubprocessorTable caption="Platform subprocessors" rows={PLATFORM_SUBPROCESSORS} />
      </section>
      <section className="space-y-3">
        <h2 className="text-[18px] font-semibold">Chosen by each workspace</h2>
        <p className="max-w-2xl text-[14px] text-[var(--on-surface-variant)]">
          These are only used when a workspace connects its own account. The workspace&apos;s agreement
          with that provider applies.
        </p>
        <SubprocessorTable caption="Workspace-selected subprocessors" rows={WORKSPACE_SUBPROCESSORS} />
      </section>
    </article>
  );
}
