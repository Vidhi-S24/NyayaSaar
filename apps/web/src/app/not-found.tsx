import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-center px-6">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-2xl font-serif text-muted-foreground">
        404
      </div>
      <h1 className="font-serif text-2xl font-semibold text-foreground">Page not found</h1>
      <p className="text-sm text-muted-foreground">This page does not exist or has been moved.</p>
      <Button asChild variant="outline" size="sm">
        <Link href="/dashboard">Go to Dashboard</Link>
      </Button>
    </div>
  );
}

