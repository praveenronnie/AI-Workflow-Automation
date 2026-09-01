import { useStore } from "@/store/useStore";

export function ActivitySection() {
  const { activityLog } = useStore();

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium">Activity</h2>

      <div className="space-y-1 rounded-md border p-3 max-h-[200px] overflow-y-auto">
        {activityLog.map((entry, index) => (
          <div
            key={index}
            className="flex items-center gap-2 text-xs text-muted-foreground"
          >
            <span className="size-1.5 rounded-full bg-muted-foreground/40 shrink-0" />
            <span>{entry}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
