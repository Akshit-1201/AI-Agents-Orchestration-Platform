"use client";

import { useEffect } from "react";
import { animate, motion, useMotionValue, useTransform } from "framer-motion";

export function AnimatedNumber({
  value,
  format,
}: {
  value: number;
  format?: (n: number) => string;
}) {
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) =>
    format ? format(v) : Math.round(v).toLocaleString(),
  );
  useEffect(() => {
    const controls = animate(mv, value, { duration: 0.5, ease: "easeOut" });
    return () => controls.stop();
  }, [value, mv]);
  return <motion.span>{text}</motion.span>;
}
