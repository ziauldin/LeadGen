"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/layout/page-header";
import { ProviderSettingsPanel } from "@/components/settings/provider-settings-panel";
import { settingsApi } from "@/lib/api/endpoints";
import { settingsSchema, type SettingsFormValues } from "@/lib/validations/forms";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
  });

  const { data: suppressions } = useQuery({
    queryKey: ["suppressions"],
    queryFn: settingsApi.listSuppressions,
  });

  const [suppressionEmail, setSuppressionEmail] = useState("");

  const {
    register,
    handleSubmit,
    reset,
    formState: { isSubmitting },
  } = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      sender_name: "",
      sender_company: "",
      business_address: "",
    },
  });

  useEffect(() => {
    if (data) {
      reset({
        sender_name: data.sender_name ?? "",
        sender_company: data.sender_company ?? "",
        business_address: data.business_address ?? "",
      });
    }
  }, [data, reset]);

  const saveMutation = useMutation({
    mutationFn: (values: SettingsFormValues) =>
      settingsApi.update({
        sender_name: values.sender_name || null,
        sender_company: values.sender_company || null,
        business_address: values.business_address || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Settings saved");
    },
  });

  const addSuppressionMutation = useMutation({
    mutationFn: () =>
      settingsApi.createSuppression({
        email: suppressionEmail,
        reason: "manual",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppressions"] });
      setSuppressionEmail("");
      toast.success("Suppression added");
    },
    onError: () => toast.error("Could not add suppression"),
  });

  const deleteSuppressionMutation = useMutation({
    mutationFn: (id: number) => settingsApi.deleteSuppression(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppressions"] });
      toast.success("Suppression removed");
    },
  });

  return (
    <div>
      <PageHeader title="Settings" description="Sender identity, providers, and suppressions." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Sender profile</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={handleSubmit((values) => saveMutation.mutate(values))}
              className="space-y-4"
            >
              <div className="space-y-2">
                <label className="text-sm font-medium">Sender name</label>
                <Input {...register("sender_name")} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Company</label>
                <Input {...register("sender_company")} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Business address</label>
                <Input {...register("business_address")} />
              </div>
              <Button type="submit" disabled={isSubmitting || saveMutation.isPending}>
                Save settings
              </Button>
            </form>
          </CardContent>
        </Card>
        <ProviderSettingsPanel />
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Suppressions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="email@example.com"
                value={suppressionEmail}
                onChange={(e) => setSuppressionEmail(e.target.value)}
              />
              <Button
                onClick={() => addSuppressionMutation.mutate()}
                disabled={!suppressionEmail || addSuppressionMutation.isPending}
              >
                Add
              </Button>
            </div>
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {suppressions?.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.email ?? item.domain}</TableCell>
                      <TableCell>{item.reason}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => deleteSuppressionMutation.mutate(item.id)}
                        >
                          Remove
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
