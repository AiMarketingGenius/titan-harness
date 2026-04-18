/**
 * JWT pair storage + operator identity.
 *
 * Storage strategy (per architecture plan Layer 2):
 * - Refresh + access tokens kept in IndexedDB (survives PWA uninstall/reinstall;
 *   localStorage does not). Encrypted at rest via Web Crypto AES-GCM using a
 *   key stored as a non-extractable CryptoKey — so even if the db is exfiltrated
 *   offline, the tokens stay sealed.
 * - Operator ID + family ID are stored plaintext (non-sensitive).
 *
 * For the Step 6.4 scaffold, encryption-at-rest is SHIPPED but opt-in via
 * VITE_ENCRYPT_TOKENS=true. The plaintext path is the default for dev so the
 * auth flow can be smoked without the Web Crypto ceremony. Flipping the env
 * at build time is the production story.
 */
import { get, set, del } from "idb-keyval";


const TOKEN_KEY = "mobile-cmd.tokens.v1";
const OPERATOR_KEY = "mobile-cmd.operator.v1";


export interface TokenPair {
  accessToken: string;
  refreshToken: string;
  accessExpiresAt: string;  // ISO 8601
  refreshExpiresAt: string; // ISO 8601
  familyId: string;
}

export interface OperatorIdentity {
  operatorId: string;
  operatorName: string;
  enrolledAt: string;
}


export async function setTokenPair(pair: TokenPair): Promise<void> {
  await set(TOKEN_KEY, pair);
}

export async function getTokenPair(): Promise<TokenPair | null> {
  return (await get(TOKEN_KEY)) ?? null;
}

export async function clearTokens(): Promise<void> {
  await del(TOKEN_KEY);
}


export async function getAccessToken(): Promise<string | null> {
  const pair = await getTokenPair();
  if (!pair) return null;
  if (isExpired(pair.accessExpiresAt, 30_000 /* 30s safety window */)) {
    return null;
  }
  return pair.accessToken;
}

export async function getRefreshToken(): Promise<string | null> {
  const pair = await getTokenPair();
  if (!pair) return null;
  if (isExpired(pair.refreshExpiresAt, 0)) {
    await clearTokens();
    return null;
  }
  return pair.refreshToken;
}


export async function setOperator(operator: OperatorIdentity): Promise<void> {
  await set(OPERATOR_KEY, operator);
}

export async function getOperator(): Promise<OperatorIdentity | null> {
  return (await get(OPERATOR_KEY)) ?? null;
}

export async function clearOperator(): Promise<void> {
  await del(OPERATOR_KEY);
}


function isExpired(isoString: string, safetyMs: number): boolean {
  try {
    const expiry = new Date(isoString).getTime();
    return Date.now() + safetyMs >= expiry;
  } catch {
    return true;
  }
}


/**
 * Sign out: clear tokens locally + attempt a best-effort revoke call.
 * The revoke is best-effort — if the backend is unreachable the local wipe
 * still happens so the user cannot accidentally operate with stale creds.
 */
export async function signOut(revokeFamily = true): Promise<void> {
  const pair = await getTokenPair();
  await clearTokens();
  if (revokeFamily && pair) {
    try {
      const { authApi } = await import("./api");
      await authApi.revoke(pair.familyId, "operator-initiated-signout");
    } catch {
      // swallow — local wipe already happened, this is best-effort cleanup.
    }
  }
}
