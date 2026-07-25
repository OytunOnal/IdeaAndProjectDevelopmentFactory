"use client";

import { Button } from "@/components/ui/button";

export function StatusBar() {
  return (
    <div className="flex h-8 items-center justify-between border-t border-border bg-muted/50 px-4 text-xs text-muted-foreground">
      <div className="flex items-center gap-4">
        <span>Phase: Idle</span>
        <span>Agent: --</span>
      </div>
      <div className="flex items-center gap-4">
        <span>Cost: $0.00</span>
        <span>0:00</span>
        <Button variant="ghost" size="sm" className="h-5 px-2 text-xs" disabled>
          Stop
        </Button>
      </div>
    </div>
  );
}
