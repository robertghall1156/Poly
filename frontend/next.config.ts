import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      { source: "/today", destination: "/discover", permanent: false },
      { source: "/stories", destination: "/discover", permanent: false },
      { source: "/stories/:id", destination: "/discover/stories/:id", permanent: false },
      { source: "/principles", destination: "/think?tab=beliefs", permanent: false },
      { source: "/principles/:id", destination: "/think/beliefs/:id", permanent: false },
      { source: "/research", destination: "/discover?tab=research", permanent: false },
      { source: "/content", destination: "/library?tab=content", permanent: false },
      { source: "/content/:id", destination: "/library/content/:id", permanent: false },
      { source: "/videos", destination: "/library?tab=videos", permanent: false },
      { source: "/videos/:id", destination: "/library/videos/:id", permanent: false },
      { source: "/book", destination: "/library?tab=book", permanent: false },
      { source: "/think/briefs/:id", destination: "/think/positions/:id", permanent: false },
    ];
  },
};

export default nextConfig;
