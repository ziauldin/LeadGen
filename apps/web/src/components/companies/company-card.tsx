import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Company } from "@/lib/api/types";

export function CompanyCard({ company }: { company: Company }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{company.name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        <p>{company.domain ?? company.website ?? "No website"}</p>
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{company.enrichment_status}</Badge>
          {company.industry ? <Badge variant="outline">{company.industry}</Badge> : null}
        </div>
        {company.enrichment_message ? <p>{company.enrichment_message}</p> : null}
      </CardContent>
    </Card>
  );
}
