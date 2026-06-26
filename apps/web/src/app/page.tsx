import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <div className="flex items-center gap-2">
            <CardTitle>LeadsGen</CardTitle>
            <Badge variant="secondary">MVP</Badge>
          </div>
          <CardDescription>
            B2B lead-intelligence and outreach workflow. Sign in to manage niches,
            leads, campaigns, and replies.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Link href="/login" className={cn(buttonVariants())}>
            Sign in
          </Link>
          <Link href="/dashboard" className={cn(buttonVariants({ variant: "outline" }))}>
            Dashboard
          </Link>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className={cn(buttonVariants({ variant: "outline" }))}
          >
            API docs
          </a>
        </CardContent>
      </Card>
    </main>
  );
}
