"use client";

import { CrmPage } from "@/components/crm/crm-page";
import { DealsBoard } from "@/components/crm/deals-board";

export default function DealsPage() {
  return (
    <CrmPage title="Deals" description="Every opportunity by stage. Drag cards between columns, or use each card's stage menu.">
      <DealsBoard />
    </CrmPage>
  );
}
