import type { ReactNode } from "react";
export const metadata = { title: "Patamaps catalog fixture" };
export default function Layout({ children }: { children: ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
