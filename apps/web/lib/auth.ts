import { randomBytes } from "node:crypto";

import bcrypt from "bcryptjs";
import { cookies, headers } from "next/headers";
import { cache } from "react";

import { q, qOne } from "./db";

export const SESSION_COOKIE = "artemis_session";
const SESSION_TTL_DAYS = 30;
const BCRYPT_ROUNDS = 12;

export interface User {
  id: number;
  email: string;
  display_name: string;
  avatar_url: string | null;
  created_at: Date;
}

interface UserRow extends User {
  password_hash: string;
}

interface SessionRow {
  id: string;
  user_id: number;
  expires_at: Date;
}

/* -------------------------------------------------------------------------- */
/* Password hashing                                                            */
/* -------------------------------------------------------------------------- */

export function hashPassword(plain: string): Promise<string> {
  return bcrypt.hash(plain, BCRYPT_ROUNDS);
}

export function verifyPassword(plain: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plain, hash);
}

/* -------------------------------------------------------------------------- */
/* Registration + login                                                        */
/* -------------------------------------------------------------------------- */

export interface RegisterInput {
  email: string;
  password: string;
  displayName: string;
}

export async function registerUser(input: RegisterInput): Promise<User> {
  const email = input.email.trim().toLowerCase();
  const displayName = input.displayName.trim();
  if (!email || !email.includes("@")) throw new AuthError("bad_email", "invalid email");
  if (input.password.length < 8) throw new AuthError("weak_password", "password must be at least 8 characters");
  if (!displayName) throw new AuthError("bad_display_name", "display name is required");

  const existing = await qOne<{ id: number }>(
    `SELECT id FROM "user" WHERE LOWER(email) = LOWER($1)`,
    [email],
  );
  if (existing) throw new AuthError("email_taken", "an account with this email already exists");

  const password_hash = await hashPassword(input.password);
  const row = await qOne<User>(
    `INSERT INTO "user"(email, password_hash, display_name)
     VALUES ($1, $2, $3)
     RETURNING id, email, display_name, avatar_url, created_at`,
    [email, password_hash, displayName],
  );
  if (!row) throw new AuthError("internal", "failed to create user");

  // Auto-create the corresponding climber row so uploads can link to it
  // without an extra UI step. Best-effort — uniqueness on LOWER(name) will
  // skip if the name collides.
  await q(
    `INSERT INTO climber(name, user_id) VALUES ($1, $2)
     ON CONFLICT (LOWER(name)) DO UPDATE
       SET user_id = COALESCE(climber.user_id, EXCLUDED.user_id)`,
    [displayName, row.id],
  );
  return row;
}

export async function loginUser(email: string, password: string): Promise<User> {
  const row = await qOne<UserRow>(
    `SELECT id, email, password_hash, display_name, avatar_url, created_at
       FROM "user" WHERE LOWER(email) = LOWER($1)`,
    [email.trim()],
  );
  if (!row) throw new AuthError("invalid_credentials", "email or password is incorrect");
  const ok = await verifyPassword(password, row.password_hash);
  if (!ok) throw new AuthError("invalid_credentials", "email or password is incorrect");
  // Strip the password hash from the returned User shape.
  const { password_hash: _ph, ...user } = row;
  void _ph;
  return user;
}

/* -------------------------------------------------------------------------- */
/* Session lifecycle                                                           */
/* -------------------------------------------------------------------------- */

export async function createSession(userId: number): Promise<string> {
  const id = randomBytes(32).toString("hex");
  const expires = new Date(Date.now() + SESSION_TTL_DAYS * 24 * 60 * 60 * 1000);
  const hdrs = await headers();
  await q(
    `INSERT INTO session(id, user_id, expires_at, user_agent, ip)
     VALUES ($1, $2, $3, $4, $5)`,
    [
      id,
      userId,
      expires,
      hdrs.get("user-agent") ?? null,
      hdrs.get("x-forwarded-for")?.split(",")[0].trim() ?? null,
    ],
  );
  const c = await cookies();
  c.set(SESSION_COOKIE, id, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires,
  });
  return id;
}

export async function destroySession(): Promise<void> {
  const c = await cookies();
  const sid = c.get(SESSION_COOKIE)?.value;
  if (sid) {
    await q(`DELETE FROM session WHERE id = $1`, [sid]);
    c.delete(SESSION_COOKIE);
  }
}

/** Look up the current user from the request cookie. Cached per request via
 *  React.cache so multiple components can call it without N round-trips. */
export const currentUser = cache(async (): Promise<User | null> => {
  const c = await cookies();
  const sid = c.get(SESSION_COOKIE)?.value;
  if (!sid) return null;
  const row = await qOne<User & { expires_at: Date }>(
    `SELECT u.id, u.email, u.display_name, u.avatar_url, u.created_at,
            s.expires_at
       FROM session s
       JOIN "user" u ON u.id = s.user_id
      WHERE s.id = $1`,
    [sid],
  );
  if (!row) return null;
  if (new Date(row.expires_at).getTime() < Date.now()) {
    // Expired — clean up.
    await q(`DELETE FROM session WHERE id = $1`, [sid]).catch(() => {});
    return null;
  }
  const { expires_at: _expires, ...user } = row;
  void _expires;
  return user;
});

/* -------------------------------------------------------------------------- */
/* Errors                                                                      */
/* -------------------------------------------------------------------------- */

export class AuthError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
    this.name = "AuthError";
  }
}
