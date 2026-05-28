import Link from "next/link";
import { redirect } from "next/navigation";

import { BrandBar } from "@/components/BrandBar";
import { UploadForm } from "@/components/UploadForm";
import { currentUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function UploadPage() {
  const user = await currentUser();
  if (!user) redirect("/sign-in?next=/upload");
  return (
    <div className="app-shell">
      <BrandBar active="upload" user={user} />
      <Link href="/" className="back-link">
        ‹ back to feed
      </Link>

      <h1 className="page-h1">upload a climb</h1>
      <div className="page-sub">
        30–90 second portrait clip works best. we detect pose, time the send,
        score smoothness, and cut the highlight.
      </div>

      <UploadForm defaultClimber={user.display_name} />
    </div>
  );
}
