import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'HireSystem — AI Candidate Evaluator',
  description: 'Score candidates across 9 dimensions using public profile data and Claude AI.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css"
        />
      </head>
      <body>{children}</body>
    </html>
  )
}