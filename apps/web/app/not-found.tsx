import Link from "next/link";

export default function NotFound() {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui", padding: 40 }}>
        <h1>404 — Page not found</h1>
        <Link href="/en">Go to 2ajar</Link>
      </body>
    </html>
  );
}
