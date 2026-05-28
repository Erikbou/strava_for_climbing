import Link from "next/link";

import { BrandBar } from "@/components/BrandBar";
import { UploadForm } from "@/components/UploadForm";

export default function UploadPage() {
  return (
    <div className="app-shell">
      <BrandBar active="upload" />
      <Link href="/" className="back-link">
        ‹ back to feed
      </Link>

      <h1 className="page-h1">upload a climb</h1>
      <div className="page-sub">
        30–90 second portrait clip works best. we detect pose, time the send,
        score smoothness, and cut the highlight.
      </div>

      <UploadForm />
    </div>
  );
}
