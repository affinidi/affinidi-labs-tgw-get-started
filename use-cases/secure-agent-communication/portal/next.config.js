/** @type {import('next').NextConfig} */
const nextConfig = {
    // Allows running two portal instances from the same dir with separate caches
    distDir: process.env.NEXT_DIST_DIR || ".next",
};

module.exports = nextConfig;
