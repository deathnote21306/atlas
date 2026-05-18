export function SkeletonLine({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[#21262d] ${className}`} />;
}

export function SkeletonCard() {
  return (
    <div className="rounded-[10px] border border-[#21262d] bg-[#161b22] p-4 space-y-3">
      <SkeletonLine className="h-4 w-1/3" />
      <SkeletonLine className="h-3 w-full" />
      <SkeletonLine className="h-3 w-2/3" />
    </div>
  );
}
