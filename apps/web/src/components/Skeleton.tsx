export function SkeletonLine({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-ink-100 ${className}`} />;
}

export function SkeletonCard() {
  return (
    <div className="rounded-md border border-ink-100 bg-white p-4 space-y-3">
      <SkeletonLine className="h-4 w-1/3" />
      <SkeletonLine className="h-3 w-full" />
      <SkeletonLine className="h-3 w-2/3" />
    </div>
  );
}
