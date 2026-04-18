/**
 * WebAuthn registration + authentication flows.
 *
 * Wraps @simplewebauthn/browser with the backend API calls so screens
 * consume a clean `register()` / `authenticate()` pair without caring
 * about the attestation-options dance.
 */
import {
  startRegistration,
  startAuthentication,
} from "@simplewebauthn/browser";

import { authApi } from "./api";
import { setOperator, setTokenPair, type OperatorIdentity, type TokenPair } from "./auth";


export interface RegisterOpts {
  operatorId: string;
  operatorName: string;
}


export async function register(opts: RegisterOpts): Promise<OperatorIdentity> {
  const options = await authApi.registerBegin({
    operator_id: opts.operatorId,
    operator_name: opts.operatorName,
  });
  // @simplewebauthn/browser type expects PublicKeyCredentialCreationOptionsJSON; backend returns dict.
  const credential = await startRegistration(options as never);
  const result = await authApi.registerVerify(opts.operatorId, credential);
  if (result.status !== "ok") {
    throw new Error(`register_verify failed: ${JSON.stringify(result)}`);
  }

  const identity: OperatorIdentity = {
    operatorId: opts.operatorId,
    operatorName: opts.operatorName,
    enrolledAt: new Date().toISOString(),
  };
  await setOperator(identity);
  return identity;
}


export async function authenticate(operatorId: string): Promise<TokenPair> {
  const options = await authApi.authenticateBegin({ operator_id: operatorId });
  const credential = await startAuthentication(options as never);
  const pair = await authApi.authenticateVerify(operatorId, credential);

  const tokenPair: TokenPair = {
    accessToken: pair.access_token,
    refreshToken: pair.refresh_token,
    accessExpiresAt: pair.access_expires_at,
    refreshExpiresAt: pair.refresh_expires_at,
    familyId: pair.family_id,
  };
  await setTokenPair(tokenPair);
  return tokenPair;
}


export function isPlatformAuthenticatorAvailable(): boolean {
  return (
    typeof window !== "undefined" &&
    "PublicKeyCredential" in window &&
    typeof (window.PublicKeyCredential as unknown as {
      isUserVerifyingPlatformAuthenticatorAvailable?: () => Promise<boolean>
    }).isUserVerifyingPlatformAuthenticatorAvailable === "function"
  );
}
