import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI Operations Console',
  description: 'Operations console for autonomous AI agent workflow orchestration with human approval and audit trails.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
