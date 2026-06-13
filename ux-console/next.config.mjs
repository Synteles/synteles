/** @type {import('next').NextConfig} */

// Allow direct browser uploads to the S3/MinIO endpoint (presigned POST URLs).
// Defaults to the AWS S3 wildcard. Set S3_PUBLIC_ENDPOINT_URL to override
// (e.g. http://localhost:9000 for local MinIO).
const s3Origin = process.env.S3_PUBLIC_ENDPOINT_URL
  ? new URL(process.env.S3_PUBLIC_ENDPOINT_URL).origin
  : 'https://*.amazonaws.com'

const connectSrc = ["'self'", s3Origin].join(' ')

const nextConfig = {
  output: 'standalone',
  experimental: {
    turbo: false,
  },
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
