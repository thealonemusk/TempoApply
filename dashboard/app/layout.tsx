import type { Metadata, Viewport } from 'next';
import './globals.css';
import { ThemeProvider } from '@/components/ThemeProvider';

export const metadata: Metadata = {
  title: 'TempoApply',
  description: 'Job discovery for early-career engineers',
  icons: {
    icon: '/vercel.png',
  },
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
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
