import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "IndustryNetworkMap — 台股產業鏈知識圖譜",
  description: "台股產業鏈知識圖譜 Web App",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body>
        <header className="topnav">
          <Link href="/" className="brand">IndustryNetworkMap</Link>
          <nav>
            <Link href="/">搜尋</Link>
            <Link href="/demand-shock">Demand Shock</Link>
            <Link href="/supply-disruption">供應中斷</Link>
            <Link href="/analysis">產業分析</Link>
            <Link href="/ask">提問</Link>
            <Link href="/review">審核</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
