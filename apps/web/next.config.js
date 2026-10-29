/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow importing from @nyayasaar/shared workspace package
  transpilePackages: ["@nyayasaar/shared"],
  // Env vars exposed to the browser — never put secrets here
  env: {},
};

module.exports = nextConfig;

