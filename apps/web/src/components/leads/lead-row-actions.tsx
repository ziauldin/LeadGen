"use client";

import Link from "next/link";
import { Eye, MailPlus, MoreHorizontal, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Lead } from "@/lib/api/types";

/** Per-row menu; a real button so it's reachable with Tab and opens with Enter/Space. */
export function LeadRowActions({ lead, onDelete }: { lead: Lead; onDelete: (lead: Lead) => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${lead.full_name}`} />
        }
      >
        <MoreHorizontal aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuItem render={<Link href={`/leads/${lead.id}`} />}>
          <Eye aria-hidden />
          View details
        </DropdownMenuItem>
        <DropdownMenuItem render={<Link href={`/email-studio?lead_id=${lead.id}`} />}>
          <MailPlus aria-hidden />
          Write email
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={() => onDelete(lead)}>
          <Trash2 aria-hidden />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
