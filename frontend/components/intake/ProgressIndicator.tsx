"use client";

type ProgressIndicatorProps = {
  currentLayer: number;
  labels: string[];
};

export default function ProgressIndicator({ currentLayer, labels }: ProgressIndicatorProps) {
  return (
    <div className="mt-6 flex flex-wrap gap-2" data-testid="progress-indicator">
      {labels.map((label, idx) => {
        const layerNum = idx + 1;
        const isActive = currentLayer === layerNum;
        const isDone = currentLayer > layerNum;
        return (
          <span
            key={label}
            data-testid={`progress-chip-${layerNum}`}
            data-active={isActive ? "true" : "false"}
            data-done={isDone ? "true" : "false"}
            className={`status-chip ${
              isDone
                ? "bg-mint/50 text-trust"
                : isActive
                  ? "bg-trust text-white"
                  : "bg-slate-100 text-slate-500"
            }`}
          >
            {isDone ? "✓" : layerNum}. {label}
          </span>
        );
      })}
    </div>
  );
}
