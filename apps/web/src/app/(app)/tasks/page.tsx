"use client";

import { CrmPage } from "@/components/crm/crm-page";
import { TasksList } from "@/components/crm/tasks-list";

export default function TasksPage() {
  return (
    <CrmPage title="Tasks" description="Follow-ups and reminders. You get a notification when a task is due.">
      <TasksList />
    </CrmPage>
  );
}
