/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [{ key: 'X-App', value: 'TempoApply' }],
      },
    ];
  },
};

export default nextConfig;
