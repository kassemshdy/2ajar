import Link from "next/link";

export default function NotFound() {
  return (
    <html lang="ar" dir="rtl">
      <body style={{ fontFamily: "system-ui", padding: 40 }}>
        <h1>404 — الصفحة غير موجودة</h1>
        <p>
          <Link href="/ar">العودة إلى إيجار</Link>
        </p>
        <p dir="ltr" lang="en">
          <Link href="/en">Page not found — go to 2ajar (English)</Link>
        </p>
      </body>
    </html>
  );
}
