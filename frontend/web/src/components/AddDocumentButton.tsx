import { useState, useRef } from "react";
import { Plus, Upload, X, FileText } from "lucide-react";
import { useStore, type Document } from "@/store/useStore";
import { Button } from "@/components/ui/button";
import { uploadMultipleFiles } from "@/lib/messaging";

type DocType = "handwritten" | "scanned" | "image" | "zip";

interface PendingFile {
  file: File;
  docType: DocType;
}

export function AddDocumentButton() {
  const {
    addDocument,
    addActivity,
    isUploading,
    setIsUploading,
    uploadProgress,
    setUploadProgress,
  } = useStore();

  const [open, setOpen] = useState(false);
  const [files, setFiles] = useState<PendingFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selected = Array.from(e.target.files).map((file) => {
      const isPdf = /\.pdf$/i.test(file.name);
      const isZip = /\.zip$/i.test(file.name);
      let docType: DocType = "scanned";
      if (isPdf) docType = "scanned";
      else if (isZip) docType = "zip";
      else docType = "image";
      return { file, docType };
    });
    setFiles((prev) => [...prev, ...selected]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removePendingFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const changeDocType = (idx: number, newType: DocType) => {
    setFiles((prev) =>
      prev.map((f, i) => (i === idx ? { ...f, docType: newType } : f)),
    );
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setIsUploading(true);
    setUploadProgress(0);

    try {
      const fileData = await Promise.all(
        files.map(async ({ file, docType }) => {
          return new Promise<{ base64: string; name: string; type: string; docType: string }>(
            (resolve, reject) => {
              const reader = new FileReader();
              reader.onprogress = (event) => {
                if (event.lengthComputable) {
                  setUploadProgress(
                    Math.round((event.loaded / event.total) * 30),
                  );
                }
              };
              reader.onload = () => {
                const base64 = (reader.result as string).split(",")[1];
                resolve({ base64, name: file.name, type: file.type, docType });
              };
              reader.onerror = () => reject(new Error("File read error"));
              reader.readAsDataURL(file);
            },
          );
        }),
      );

      setUploadProgress(40);
      addActivity(`Uploading ${files.length} file(s)...`);

      const response = await uploadMultipleFiles(fileData);

      if (response.success) {
        setUploadProgress(100);
        files.forEach(({ file, docType }) => {
          const newDoc: Document = {
            id: crypto.randomUUID(),
            name: file.name,
            docType: docType,
          };
          addDocument(newDoc);
          addActivity(`Upload complete: ${file.name}`);
        });
        setFiles([]);
        setOpen(false);
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

  const isPdfFile = (file: File) => /\.pdf$/i.test(file.name);

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="w-full"
        onClick={() => setOpen(true)}
        disabled={isUploading}
      >
        <Plus className="size-4" />
        Add Documents
      </Button>

      {open && (
        <div className="fixed inset-0 z-[11000] flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
          />
          <div className="relative z-10 w-full max-w-md rounded-lg border bg-background p-5 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold">Add Documents</h3>
              <button
                onClick={() => setOpen(false)}
                className="rounded-md p-1 hover:bg-muted"
                aria-label="Close"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="space-y-2 mb-4">
              <label className="text-xs font-medium text-muted-foreground">
                Select files (PDF, images, ZIP)
              </label>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.png,.jpg,.jpeg,.gif,.bmp,.webp,.zip"
                onChange={handleFileSelect}
                className="block w-full text-xs text-muted-foreground
                           file:mr-2 file:py-1.5 file:px-3
                           file:rounded-md file:border-0
                           file:text-xs file:font-medium
                           file:bg-primary file:text-primary-foreground
                           hover:file:bg-primary/90
                           cursor-pointer"
              />
            </div>

            {files.length > 0 && (
              <div className="space-y-2 mb-4 max-h-48 overflow-y-auto">
                <p className="text-xs text-muted-foreground">
                  {files.length} file{files.length > 1 ? "s" : ""} added
                </p>
                {files.map(({ file, docType }, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2 rounded-md border px-3 py-2 text-xs"
                  >
                    <FileText className="size-4 shrink-0 text-muted-foreground" />
                    <span className="truncate flex-1">{file.name}</span>
                    {isPdfFile(file) ? (
                      <select
                        value={docType}
                        onChange={(e) =>
                          changeDocType(idx, e.target.value as DocType)
                        }
                        className="rounded border px-2 py-0.5 text-xs bg-background"
                      >
                        <option value="scanned">Scanned</option>
                        <option value="handwritten">Handwritten</option>
                      </select>
                    ) : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted">
                        {docType === "zip" ? "ZIP" : "Image"}
                      </span>
                    )}
                    <button
                      onClick={() => removePendingFile(idx)}
                      className="shrink-0 rounded p-0.5 hover:bg-muted"
                      aria-label={`Remove ${file.name}`}
                    >
                      <X className="size-3 text-destructive" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {isUploading && uploadProgress > 0 && (
              <div className="mb-4">
                <div className="h-1.5 w-full rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="text-[10px] text-muted-foreground mt-1 text-right">
                  {uploadProgress}%
                </p>
              </div>
            )}

            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOpen(false)}
                disabled={isUploading}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleUpload}
                disabled={files.length === 0 || isUploading}
              >
                <Upload className="size-3.5" />
                {isUploading ? "Uploading..." : "Upload"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
