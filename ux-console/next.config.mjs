/** @type {import('next').NextConfig} */

// Allow direct browser uploads to the S3/MinIO endpoint (presigned POST URLs).
// In production this is an amazonaws.com URL covered by the wildcard below.
// For local dev, set S3_PUBLIC_ENDPOINT_URL=http://localhost:9000 via docker-compose.
const s3PublicOrigin = process.env.S3_PUBLIC_ENDPOINT_URL
  ? new URL(process.env.S3_PUBLIC_ENDPOINT_URL).origin
  : null

const connectSrc = [
  "'self'",
  ...(s3PublicOrigin ? [s3PublicOrigin] : []),
].join(' ')

const nextConfig = {
  output: 'standalone',
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob:",
              "font-src 'self'",
              `connect-src ${connectSrc}`,
              "frame-ancestors 'none'",
            ].join('; '),
          },
        ],
      },
    ]
  },
}

export default nextConfig
