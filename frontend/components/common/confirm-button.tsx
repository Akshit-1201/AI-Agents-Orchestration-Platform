"use client";

import { useState, type ComponentProps } from "react";
import { Button } from "@/components/ui/button";

export function ConfirmButton({
  onConfirm,
  children,
  confirmLabel = "Sure?",
  ...props
}: { onConfirm: () => void; confirmLabel?: string } & ComponentProps<typeof Button>) {
  const [armed, setArmed] = useState(false);
  return (
    <Button
      {...props}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (armed) {
          onConfirm();
          setArmed(false);
        } else {
          setArmed(true);
          setTimeout(() => setArmed(false), 2500);
        }
      }}
    >
      {armed ? confirmLabel : children}
    </Button>
  );
}
