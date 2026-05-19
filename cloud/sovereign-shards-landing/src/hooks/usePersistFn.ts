import { useRef } from "react";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyFunction = (...args: any[]) => any;

export function usePersistFn<T extends AnyFunction>(fn: T): T {
  const fnRef = useRef<T>(fn);
  fnRef.current = fn;

  const persistFn = useRef<T | null>(null);
  if (!persistFn.current) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    persistFn.current = function (this: unknown, ...args: any[]) {
      return fnRef.current!.apply(this, args);
    } as T;
  }

  return persistFn.current!;
}
