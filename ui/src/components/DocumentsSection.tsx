import { FileText } from "lucide-react";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/button";
import { AddDocumentButton } from "@/components/AddDocumentButton";

export function DocumentsSection() {
  const { documents, setActiveDrawer, domain } = useStore();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Documents</h2>
        <span className="text-xs text-muted-foreground">
          {documents.length} Document{documents.length !== 1 ? "s" : ""} |{" "}
          <span className="font-mono">{domain}</span>
        </span>
      </div>

      <div className="space-y-2">
        <AddDocumentButton />

        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => setActiveDrawer("documents")}
        >
          <FileText className="size-4" />
          Manage Documents
        </Button>
      </div>
    </div>
  );
}
