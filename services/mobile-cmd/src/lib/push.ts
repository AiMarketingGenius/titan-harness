/**
 * Web Push subscription helpers — wraps browser PushManager + backend API.
 *
 * iOS 16.4+ constraints:
 * - requires standalone PWA install (home-screen add) before PushManager.subscribe resolves
 * - subscriptions expire after ~30 days of inactivity with no auto-renew
 * - no silent push; every push must show a user-visible notification
 *
 * VAPID_PUBLIC_KEY must be built into the bundle via VITE_VAPID_PUBLIC_KEY
 * (base64url, uncompressed 65-byte P-256 point). The matching private key
 * lives on the backend for JWT-bound push send.
 */
import { pushApi } from "./api";


const VAPID_PUBLIC_KEY = (import.meta.env.VITE_VAPID_PUBLIC_KEY as string | undefined) || "";


export function canSubscribe(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    !!VAPID_PUBLIC_KEY
  );
}


export async function requestPermission(): Promise<NotificationPermission> {
  if (!("Notification" in window)) return "denied";
  if (Notification.permission === "granted" || Notification.permission === "denied") {
    return Notification.permission;
  }
  return Notification.requestPermission();
}


export async function subscribePush(operatorId: string): Promise<{ id: string }> {
  if (!canSubscribe()) {
    throw new Error(
      "Push not available — requires a PWA home-screen install + VAPID_PUBLIC_KEY configured",
    );
  }
  const permission = await requestPermission();
  if (permission !== "granted") {
    throw new Error(`Notification permission ${permission}`);
  }

  const reg = await navigator.serviceWorker.ready;
  const existing = await reg.pushManager.getSubscription();
  const subscription = existing ?? await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY).buffer as ArrayBuffer,
  });

  const json = subscription.toJSON();
  const keys = json.keys || {};
  return pushApi.subscribe({
    operator_id: operatorId,
    endpoint: json.endpoint!,
    keys: { p256dh: keys.p256dh ?? "", auth: keys.auth ?? "" },
    user_agent: navigator.userAgent,
  });
}


export async function unsubscribePush(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (sub) await sub.unsubscribe();
}


function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; ++i) output[i] = raw.charCodeAt(i);
  return output;
}
