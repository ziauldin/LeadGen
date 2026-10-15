"use client";

import { useParams } from "next/navigation";
import { ReplyDetailView } from "@/components/replies/reply-detail";

export default function ReplyDetailPage() {
  const params = useParams<{ id: string }>();
  return <ReplyDetailView id={Number(params.id)} />;
}
