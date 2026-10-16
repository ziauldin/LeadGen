import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="text-sm font-semibold text-[var(--primary)]">404</p>
      <h1 className="text-2xl font-bold">Page not found</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        The page you were looking for doesn&apos;t exist or has moved.
      </p>
      <Link href="/dashboard" className={buttonVariants()}>
        Go to dashboard
      </Link>
    </main>
  );
}
