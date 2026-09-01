import { X, Upload, Trash2, FileText, AlertTriangle } from "lucide-react";
import { useStore, type Document } from "@/store/useStore";
import { Button } from "@/features/shared/components/ui/button";
import {
  uploadMultipleFiles,
  deleteDocument,
  getFormSchema,
} from "@/lib/messaging";
import { FormFieldsTable } from "@/features/form-mapping/components/FormFieldsTable";
import { transformToSections } from "@/features/shared/lib/formatters";
import { useState, useRef, useMemo, useEffect } from "react";

// Max file size: 100MB
const MAX_FILE_SIZE = 100 * 1024 * 1024;

function DocumentRow({
  doc,
  onDelete,
}: {
  doc: Document;
  onDelete: (id: string) => void;
}) {
  const [showConfirm, setShowConfirm] = useState(false);

  if (showConfirm) {
    return (
      <div className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
        <span className="truncate">{doc.name}</span>
        <div className="flex gap-2 shrink-0">
          <Button
            variant="outline"
            size="xs"
            onClick={() => setShowConfirm(false)}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="xs"
            onClick={async () => {
              await deleteDocument(doc.id);
              onDelete(doc.id);
              setShowConfirm(false);
            }}
          >
            Delete
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
      <div className="flex items-center gap-2 truncate">
        <FileText className="size-4 shrink-0 text-muted-foreground" />
        <span className="truncate">{doc.name}</span>
        <span
          className={`text-[10px] px-1.5 py-0.5 rounded-full ${
            doc.docType === "handwritten"
              ? "bg-amber-100 text-amber-700"
              : doc.docType === "image"
                ? "bg-purple-100 text-purple-700"
                : "bg-blue-100 text-blue-700"
          }`}
        >
          {doc.docType === "handwritten"
            ? "Handwritten"
            : doc.docType === "image"
              ? "Image"
              : "Scanned"}
        </span>
      </div>
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={() => setShowConfirm(true)}
        aria-label={`Delete ${doc.name}`}
      >
        <Trash2 className="size-3.5 text-destructive" />
      </Button>
    </div>
  );
}

function DocumentsDrawerContent() {
  const {
    documents,
    addDocument,
    removeDocument,
    isUploading,
    setIsUploading,
    addActivity,
    uploadProgress,
    setUploadProgress,
    uploadDocType,
    setUploadDocType,
  } = useStore();

  const pdfInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  const uploadFiles = async (
    filesToUpload: File[],
    activeDoc: "scanned" | "handwritten",
  ) => {
    setIsUploading(true);
    setUploadProgress(0);

    // Add activity for batch upload
    if (filesToUpload.length > 1) {
      addActivity(`Uploading ${filesToUpload.length} file(s)...`);
    }

    try {
      // Read all files first
      const fileData = await Promise.all(
        filesToUpload.map(async (file) => {
          return new Promise<{ base64: string; name: string; type: string }>(
            (resolve, reject) => {
              const reader = new FileReader();
              reader.onprogress = (event) => {
                if (event.lengthComputable) {
                  const readProgress = Math.round(
                    (event.loaded / event.total) * 50,
                  );
                  setUploadProgress(readProgress);
                }
              };
              reader.onload = () => {
                const base64 = (reader.result as string).split(",")[1];
                resolve({
                  base64,
                  name: file.name,
                  type: file.type,
                });
              };
              reader.onerror = () => reject(new Error("File read error"));
              reader.readAsDataURL(file);
            },
          );
        }),
      );

      // Reading complete: 50%
      setUploadProgress(50);
      addActivity(
        `Reading complete. Uploading ${filesToUpload.length} file(s)...`,
      );

      // PDFs carry the selected sub-doc (scanned/handwritten); images and ZIPs
      // route independently to the image endpoint regardless of this value.
      const response = await uploadMultipleFiles(fileData, activeDoc);

      if (response.success) {
        // Upload complete: 100%
        setUploadProgress(100);

        filesToUpload.forEach((file) => {
          const isPdf = /\\.pdf$/i.test(file.name);
          const newDoc: Document = {
            id: crypto.randomUUID(),
            name: file.name,
            docType: isPdf ? activeDoc : "image",
          };
          addDocument(newDoc);
          addActivity(`Upload complete: ${file.name}`);
        });
      } else {
        addActivity(`Upload failed: ${response.error || "Unknown error"}`);
      }
    } catch (err) {
      addActivity(
        `Upload failed: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const runUpload = async (
    fileArray: File[],
    activeDoc: "scanned" | "handwritten",
  ) => {
    // Validate each file size
    const oversizedFiles = fileArray.filter((file) => file.size > MAX_FILE_SIZE);
    if (oversizedFiles.length > 0) {
      oversizedFiles.forEach((file) => {
        addActivity(
          `Upload failed: File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Max: 50MB`,
        );
      });
      const validFiles = fileArray.filter((file) => file.size <= MAX_FILE_SIZE);
      if (validFiles.length === 0) return;
      await uploadFiles(validFiles, activeDoc);
      return;
    }
    await uploadFiles(fileArray, activeDoc);
  };

  const handlePdfUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (e.target) e.target.value = "";
    if (!files || files.length === 0) return;
    const activeDoc = uploadDocType === "handwritten" ? "handwritten" : "scanned";
    await runUpload(Array.from(files), activeDoc);
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (e.target) e.target.value = "";
    if (!files || files.length === 0) return;
    // docType is ignored by the image/ZIP endpoint; provide a safe fallback.
    await runUpload(Array.from(files), "scanned");
  };

  // Shared drop target for both upload sections. Reuses the same routing as
  // the file-picker handlers: PDFs respect the dropdown, images/ZIPs always
  // route to the image endpoint.
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = async (e: React.DragEvent, kind: "pdf" | "image") => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    if (kind === "pdf") {
      const pdfs = files.filter((f) => /\.pdf$/i.test(f.name));
      if (pdfs.length > 0) {
        await runUpload(
          pdfs,
          uploadDocType === "handwritten" ? "handwritten" : "scanned",
        );
      }
    } else {
      const images = files.filter((f) =>
        /\.(png|jpe?g|bmp|gif|webp|zip)$/i.test(f.name),
      );
      if (images.length > 0) await runUpload(images, "scanned");
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* PDF upload section */}
      <div
        className="mb-4 space-y-2"
        onDragOver={handleDragOver}
        onDrop={(e) => handleDrop(e, "pdf")}
      >
        <label className="text-muted-foreground text-xs font-medium">
          PDF Documents
        </label>
        <select
          value={uploadDocType === "handwritten" ? "handwritten" : "scanned"}
          onChange={(e) =>
            setUploadDocType(e.target.value as "scanned" | "handwritten")
          }
          className="w-full rounded-md border bg-background px-2 py-1.5 text-xs"
          disabled={isUploading}
        >
          <option value="scanned">Scanned</option>
          <option value="handwritten">Handwritten</option>
        </select>

        {uploadDocType === "handwritten" && (
          <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <AlertTriangle className="size-3.5 mt-0.5 shrink-0 text-amber-500" />
            <p>
              Handwritten content may require different document processing.
              Please ensure documents are clear and legible for optimal results.
            </p>
          </div>
        )}

        <input
          type="file"
          accept=".pdf"
          multiple
          className="hidden"
          id="pdf-file-upload-drawer"
          onChange={handlePdfUpload}
          ref={pdfInputRef}
        />
        <label htmlFor="pdf-file-upload-drawer">
          <Button
            variant="outline"
            size="sm"
            className="w-full cursor-pointer"
            disabled={isUploading}
            asChild
          >
            <span>
              <Upload className="size-4" />
              {isUploading ? "Uploading..." : "Upload PDFs"}
            </span>
          </Button>
        </label>
        <p className="text-muted-foreground text-xs">
          Select PDFs. Choose Scanned or Handwritten for the batch.
        </p>
      </div>

      {/* Image / ZIP upload section */}
      <div
        className="mb-4 space-y-2"
        onDragOver={handleDragOver}
        onDrop={(e) => handleDrop(e, "image")}
      >
        <label className="text-muted-foreground text-xs font-medium">
          Images &amp; ZIP Archives
        </label>
        <input
          type="file"
          accept=".png,.jpg,.jpeg,.bmp,.gif,.webp,.zip"
          multiple
          className="hidden"
          id="image-file-upload-drawer"
          onChange={handleImageUpload}
          ref={imageInputRef}
        />
        <label htmlFor="image-file-upload-drawer">
          <Button
            variant="outline"
            size="sm"
            className="w-full cursor-pointer"
            disabled={isUploading}
            asChild
          >
            <span>
              <Upload className="size-4" />
              {isUploading ? "Uploading..." : "Upload Images / ZIP"}
            </span>
          </Button>
        </label>
        <div className="flex items-start gap-2 rounded-md border border-purple-200 bg-purple-50 px-3 py-2 text-xs text-purple-800">
          <AlertTriangle className="size-3.5 mt-0.5 shrink-0 text-purple-500" />
          <p>
            Images are processed with a Vision Language Model (VLM). ZIP
            archives are supported for bulk upload.
          </p>
        </div>
      </div>
      {/* Document list */}
      <div className="flex-1 overflow-y-auto space-y-2 max-h-[250px]">
        {documents.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-8">
            No documents uploaded yet
          </p>
        )}
        {documents.map((doc) => (
          <DocumentRow key={doc.id} doc={doc} onDelete={removeDocument} />
        ))}
      </div>

      {/* Upload progress bar */}
      {isUploading && (
        <div className="pt-3 space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {uploadProgress < 50
                ? "Reading file..."
                : uploadProgress < 100
                  ? "Uploading to server..."
                  : "Complete"}
            </span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-300 ease-out"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

    </div>
  );
}

export function Drawer() {
  const { activeDrawer, setActiveDrawer, formFields, mappings } = useStore();
  const [formSchema, setFormSchema] = useState<any>(null);
  const mappingsKey = Object.keys(mappings).length;

  // Reload the form schema whenever the drawer opens or the mapping / field
  // state changes, so the table always reflects the latest mapped values
  // (e.g. right after "Review Mapping" completes) instead of the snapshot
  // taken when the panel first mounted.
  useEffect(() => {
    getFormSchema().then((response) => {
      if (response.success && response.data) {
        setFormSchema(response.data);
      } else {
        console.warn("Failed to load form schema:", response.error);
      }
    });
  }, [activeDrawer, mappingsKey, formFields.length]);

  const sections = useMemo(() => {
    if (!formSchema) return [];
    return transformToSections(formFields, formSchema, mappings);
  }, [formSchema, formFields, mappings]);

  if (!activeDrawer) return null;

  return (
    <div className="fixed inset-0 z-[10000] flex">
      {/* Backdrop */}
      <div
        className="flex-1 bg-black/30"
        onClick={() => setActiveDrawer(null)}
      />

      {/* Drawer panel - dynamic width */}
      <div className="w-[min(460px,90vw)] bg-background border-l flex flex-col">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-sm font-semibold">
            {activeDrawer === "documents" && "Manage Documents"}
            {activeDrawer === "fields" && "Detected Fields"}
            {activeDrawer === "fields-table" && "Form Fields Table"}
            {activeDrawer === "mapping" && "Review Mapping"}
          </h2>
          <button
            onClick={() => setActiveDrawer(null)}
            className="rounded-md p-1 hover:bg-muted"
            aria-label="Close drawer"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {activeDrawer === "documents" && <DocumentsDrawerContent />}

          {activeDrawer === "fields" && (
            sections.length > 0 ? (
              <FormFieldsTable sections={sections} viewMode="raw" />
            ) : formFields.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-8">
                No fields detected yet. Scan a form first.
              </p>
            ) : (
              <div className="space-y-2">
                {formFields.map((field) => (
                  <div
                    key={field.field_id}
                    className="rounded-md border px-3 py-2 text-sm"
                  >
                    <div className="font-medium">{field.field_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {field.field_type}
                    </div>
                  </div>
                ))}
              </div>
            )
          )}

          {activeDrawer === "fields-table" && (
            <FormFieldsTable sections={sections} viewMode="filled" />
          )}

          {activeDrawer === "mapping" && (
            <div className="space-y-2">
              {Object.keys(mappings).length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-8">
                  No mappings generated yet.
                </p>
              )}
              {Object.entries(mappings).map(([fieldId, mapping]) => {
                const confidence = mapping.confidence ?? 0;
                let statusIcon = "✕";
                let statusColor = "text-destructive";
                if (confidence >= 0.8) {
                  statusIcon = "✓";
                  statusColor = "text-green-600";
                } else if (confidence >= 0.5) {
                  statusIcon = "⚠";
                  statusColor = "text-amber-500";
                }

                return (
                  <div
                    key={fieldId}
                    className="rounded-md border px-3 py-2 text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{fieldId}</span>
                      <span className={`${statusColor} text-xs`}>
                        {statusIcon}{" "}
                        {confidence >= 0.8
                          ? "High Confidence"
                          : confidence >= 0.5
                            ? "Needs Review"
                            : "Missing"}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      → {mapping.value || mapping.source_key || "—"}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
