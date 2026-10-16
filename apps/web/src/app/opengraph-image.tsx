import { ImageResponse } from "next/og";
import { SITE } from "@/lib/marketing";

export const alt = `${SITE.name}: ${SITE.tagline}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 80,
          background: "linear-gradient(135deg, #0b3b8c 0%, #1d4ed8 100%)",
          color: "white",
        }}
      >
        <div style={{ fontSize: 40, fontWeight: 700, opacity: 0.9 }}>{SITE.name}</div>
        <div style={{ fontSize: 72, fontWeight: 800, marginTop: 24, lineHeight: 1.1 }}>
          Outbound that respects the people you email
        </div>
        <div style={{ fontSize: 30, marginTop: 28, opacity: 0.85 }}>{SITE.tagline}</div>
      </div>
    ),
    size,
  );
}
