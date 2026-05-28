import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/AuthForm";
import { BrandBar } from "@/components/BrandBar";
import { currentUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<{ next?: string }>;
}

export default async function SignUpPage({ searchParams }: PageProps) {
  const user = await currentUser();
  if (user) redirect("/");
  const sp = await searchParams;
  return (
    <div className="app-shell">
      <BrandBar active="feed" user={null} />
      <h1 className="page-h1">create your account</h1>
      <div className="page-sub">
        get your sends, smoothness scores, and dyno counts on the feed. already
        a member?{" "}
        <Link href="/sign-in" style={{ color: "var(--amber-deep)", fontWeight: 700 }}>
          sign in
        </Link>
        .
      </div>
      <AuthForm mode="sign-up" next={sp.next ?? "/"} />
    </div>
  );
}
