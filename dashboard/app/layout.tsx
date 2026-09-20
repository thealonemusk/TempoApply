import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TempoApply — AI Job Application Agent',
  description: 'Your AI-powered job application command centre',
};

// `viewportFit: 'cover'` lets the page paint into the iPhone's safe areas; the
// bottom nav then pads itself back out with env(safe-area-inset-bottom) so it
// clears the home indicator instead of sitting under it.
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-newsprint text-ink antialiased">
        {children}
      </body>
    </html>
  );
}
