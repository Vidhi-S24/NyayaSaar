"use client";

/**
 * Sign-in / create account — single page, two modes.
 *
 * Authentication is performed by the FastAPI backend (JWT bearer tokens).
 * On success the user is redirected to the dashboard.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertCircle, Loader2, Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth/auth-context";

const signInSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

const signUpSchema = z.object({
  fullName: z.string().max(255, "Name is too long").optional(),
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z
    .string()
    .min(8, "At least 8 characters")
    .max(128, "At most 128 characters"),
});

type SignInForm = z.infer<typeof signInSchema>;
type SignUpForm = z.infer<typeof signUpSchema>;

export default function SignInPage() {
  const { status, signIn, signUp } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [authError, setAuthError] = useState<string | null>(null);

  // Already signed in? Go straight to the workspace.
  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [status, router]);

  const signInForm = useForm<SignInForm>({
    resolver: zodResolver(signInSchema),
    defaultValues: { email: "", password: "" },
  });

  const signUpForm = useForm<SignUpForm>({
    resolver: zodResolver(signUpSchema),
    defaultValues: { fullName: "", email: "", password: "" },
  });

  const onSignIn = signInForm.handleSubmit(async (values) => {
    setAuthError(null);
    try {
      await signIn(values.email, values.password);
    } catch (err) {
      setAuthError(
        err instanceof Error ? err.message : "Sign-in failed. Try again.",
      );
    }
  });

  const onSignUp = signUpForm.handleSubmit(async (values) => {
    setAuthError(null);
    try {
      await signUp(values.email, values.password, values.fullName);
    } catch (err) {
      setAuthError(
        err instanceof Error ? err.message : "Registration failed. Try again.",
      );
    }
  });

  const switchMode = (next: "signin" | "signup") => {
    setMode(next);
    setAuthError(null);
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-ink-800 text-white">
            <Scale className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              NyayaSaar
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Legal case intelligence workspace
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
          {/* Mode switch */}
          <div
            className="mb-5 grid grid-cols-2 gap-1 rounded-md bg-secondary p-1"
            role="tablist"
            aria-label="Authentication mode"
          >
            <button
              type="button"
              role="tab"
              aria-selected={mode === "signin"}
              onClick={() => switchMode("signin")}
              className={`rounded px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                mode === "signin"
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "signup"}
              onClick={() => switchMode("signup")}
              className={`rounded px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                mode === "signup"
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Create account
            </button>
          </div>

          {authError && (
            <div
              role="alert"
              className="mb-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800"
            >
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {authError}
            </div>
          )}

          {mode === "signin" ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void onSignIn(e);
              }}
              noValidate
              className="flex flex-col gap-4"
            >
              <div className="flex flex-col gap-1.5">
                <label htmlFor="signin-email" className="text-xs font-medium text-foreground">
                  Email
                </label>
                <Input
                  id="signin-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@chambers.example"
                  aria-invalid={!!signInForm.formState.errors.email}
                  {...signInForm.register("email")}
                />
                {signInForm.formState.errors.email && (
                  <p className="text-xs text-red-700" role="alert">
                    {signInForm.formState.errors.email.message}
                  </p>
                )}
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="signin-password" className="text-xs font-medium text-foreground">
                  Password
                </label>
                <Input
                  id="signin-password"
                  type="password"
                  autoComplete="current-password"
                  aria-invalid={!!signInForm.formState.errors.password}
                  {...signInForm.register("password")}
                />
                {signInForm.formState.errors.password && (
                  <p className="text-xs text-red-700" role="alert">
                    {signInForm.formState.errors.password.message}
                  </p>
                )}
              </div>

              <Button type="submit" variant="teal" disabled={signInForm.formState.isSubmitting}>
                {signInForm.formState.isSubmitting && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                )}
                Sign in
              </Button>
            </form>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void onSignUp(e);
              }}
              noValidate
              className="flex flex-col gap-4"
            >
              <div className="flex flex-col gap-1.5">
                <label htmlFor="signup-name" className="text-xs font-medium text-foreground">
                  Full name <span className="text-muted-foreground">(optional)</span>
                </label>
                <Input
                  id="signup-name"
                  type="text"
                  autoComplete="name"
                  placeholder="Adv. A. Sharma"
                  aria-invalid={!!signUpForm.formState.errors.fullName}
                  {...signUpForm.register("fullName")}
                />
                {signUpForm.formState.errors.fullName && (
                  <p className="text-xs text-red-700" role="alert">
                    {signUpForm.formState.errors.fullName.message}
                  </p>
                )}
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="signup-email" className="text-xs font-medium text-foreground">
                  Email
                </label>
                <Input
                  id="signup-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@chambers.example"
                  aria-invalid={!!signUpForm.formState.errors.email}
                  {...signUpForm.register("email")}
                />
                {signUpForm.formState.errors.email && (
                  <p className="text-xs text-red-700" role="alert">
                    {signUpForm.formState.errors.email.message}
                  </p>
                )}
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="signup-password" className="text-xs font-medium text-foreground">
                  Password
                </label>
                <Input
                  id="signup-password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                  aria-invalid={!!signUpForm.formState.errors.password}
                  {...signUpForm.register("password")}
                />
                {signUpForm.formState.errors.password && (
                  <p className="text-xs text-red-700" role="alert">
                    {signUpForm.formState.errors.password.message}
                  </p>
                )}
              </div>

              <Button type="submit" variant="teal" disabled={signUpForm.formState.isSubmitting}>
                {signUpForm.formState.isSubmitting && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                )}
                Create account
              </Button>

              <p className="text-center text-xs text-muted-foreground">
                Your account is private. Cases you create are visible only to you
                until sharing is enabled.
              </p>
            </form>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          <Link href="/" className="hover:text-foreground hover:underline">
            ← Back to overview
          </Link>
        </p>
      </div>
    </main>
  );
}
