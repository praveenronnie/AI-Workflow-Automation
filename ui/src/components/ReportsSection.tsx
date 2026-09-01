import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/button";
import { RefreshCw, FileText } from "lucide-react";
import { getUserReports } from "@/lib/messaging";
import { useState } from "react";

export function ReportsSection() {
  const { userReports, setUserReports } = useStore();
  const [loading, setLoading] = useState(false);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const response = await getUserReports();
      if (response.success && Array.isArray(response.data)) {
        setUserReports(response.data);
      } else {
        console.warn("Failed to load user reports:", response.error);
      }
    } catch (err) {
      console.error("Error loading user reports:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Your Reports</h2>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={handleRefresh}
          disabled={loading}
          aria-label="Refresh reports"
        >
          <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {userReports.length === 0 && (
        <p className="text-xs text-muted-foreground text-center py-4">
          No reports found. Create a report to get started.
        </p>
      )}

      {userReports.length > 0 && (
        <div className="max-h-64 overflow-y-auto rounded-md border">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-muted/50">
              <tr className="border-b">
                <th className="text-left px-3 py-2 font-medium">Report</th>
                <th className="text-right px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {userReports.map((report: any, idx: number) => (
                <tr
                  key={report.report_id || idx}
                  className="border-b last:border-0 hover:bg-muted/30"
                >
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                      <span className="truncate max-w-[200px]">
                        {report.report_url || report.title || `Report #${idx + 1}`}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <span className="text-muted-foreground">
                      {report.status || "—"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}