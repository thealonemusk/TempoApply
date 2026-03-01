import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TempoApply — AI Job Application Agent',
  description: 'Your AI-powered job application command centre',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-base text-txt-primary antialiased bg-mesh">
        {children}
      </body>
    </html>
  );
}
