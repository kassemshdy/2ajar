// The real <html> lives in app/[locale]/layout.tsx so `lang`/`dir` follow the locale.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return children;
}
