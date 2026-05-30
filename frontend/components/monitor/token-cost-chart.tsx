"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { WsMessageData } from "@/lib/types";

export function TokenCostChart({ messages }: { messages: WsMessageData[] }) {
  const points = messages.filter((m) => m.prompt_tokens + m.completion_tokens > 0);
  const data = points.reduce<{ step: number; tokens: number }[]>((acc, m, i) => {
    const prev = i === 0 ? 0 : acc[i - 1].tokens;
    acc.push({ step: i + 1, tokens: prev + m.prompt_tokens + m.completion_tokens });
    return acc;
  }, []);

  if (data.length < 1) {
    return <p className="text-xs text-muted-foreground">No token usage yet.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={150}>
      <AreaChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
        <defs>
          <linearGradient id="tokGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" stopOpacity={0.45} />
            <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="step" hide />
        <YAxis
          width={34}
          tick={{ fontSize: 10, fill: "#64748b" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: 8,
            fontSize: 12,
          }}
          labelStyle={{ color: "#94a3b8" }}
          formatter={(v) => [`${Number(v).toLocaleString()} tokens`, "cumulative"]}
        />
        <Area
          type="monotone"
          dataKey="tokens"
          stroke="#6366f1"
          strokeWidth={2}
          fill="url(#tokGrad)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
