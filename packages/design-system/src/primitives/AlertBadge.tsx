export interface AlertBadgeProps {
  severity: "critical" | "warning" | "info";
}

const CONFIG: Record<
  AlertBadgeProps["severity"],
  { dotClass: string; textClass: string; glowStyle?: React.CSSProperties }
> = {
  critical: {
    dotClass: "bg-danger",
    textClass: "text-danger",
    glowStyle: { boxShadow: "0 0 6px 2px rgba(239,68,68,0.45)" },
  },
  warning: {
    dotClass: "bg-warning",
    textClass: "text-warning",
  },
  info: {
    dotClass: "bg-info",
    textClass: "text-info",
  },
};

export function AlertBadge({ severity }: AlertBadgeProps) {
  const { dotClass, textClass, glowStyle } = CONFIG[severity];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${textClass}`}>
      <span
        className={`inline-block h-2 w-2 rounded-full ${dotClass}`}
        style={glowStyle}
      />
      {severity}
    </span>
  );
}
