import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/AuthForm";
import { BrandBar } from "@/components/BrandBar";
import { currentUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<{ next?: string }>;
}

export default async function SignInPage({ searchParams }: PageProps) {
  const user = await currentUser();
  if (user) redirect("/");
  const sp = await searchParams;
  return (
    <div className="app-shell">
      <BrandBar active="feed" user={null} />
      <h1 className="page-h1">sign in</h1>
      <div className="page-sub">
        welcome back. don&apos;t have an account?{" "}
        <Link href="/sign-up" style={{ color: "var(--amber-deep)", fontWeight: 700 }}>
          create one
        </Link>
        .
      </div>
      <AuthForm mode="sign-in" next={sp.next ?? "/"} />
    </div>
  );
}
