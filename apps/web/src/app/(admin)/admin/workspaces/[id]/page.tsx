"use client";

import { useParams } from "next/navigation";
import { AdminWorkspacePage } from "@/components/admin/admin-workspace";

export default function Page() {
  const params = useParams<{ id: string }>();
  return <AdminWorkspacePage id={Number(params.id)} />;
}
