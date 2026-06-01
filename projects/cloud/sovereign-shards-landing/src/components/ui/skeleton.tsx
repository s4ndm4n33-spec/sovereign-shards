// Copyright (c) 2026 Mike McCollum
//
// Licensed under the Sovereign Shards License.
// See LICENSE.md for details.

import { cn } from "@/lib/utils";

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-primary/10", className)}
      {...props}
    />
  );
}

export { Skeleton };
