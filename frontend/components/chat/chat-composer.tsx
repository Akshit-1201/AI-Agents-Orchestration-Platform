"use client";

import { useState } from "react";
import { SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function ChatComposer({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");

  const submit = () => {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText("");
  };

  return (
    <div className="flex items-end gap-2 border-t border-border bg-background/60 p-3">
      <Textarea
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder={disabled ? "Waiting for reply…" : "Type a message…  (Enter to send · Shift+Enter for newline)"}
        className="max-h-40 min-h-[40px] flex-1 resize-none"
      />
      <Button onClick={submit} disabled={disabled || !text.trim()} size="icon" aria-label="Send message">
        <SendHorizontal className="size-4" />
      </Button>
    </div>
  );
}
