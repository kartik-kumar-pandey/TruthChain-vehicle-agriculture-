import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(timestamp: number | string | undefined | null): string {
  if (!timestamp) return "N/A";
  const ts = typeof timestamp === "string" ? parseInt(timestamp, 10) : timestamp;
  if (isNaN(ts)) return String(timestamp);
  // Unix timestamp in seconds vs milliseconds
  const ms = ts < 100000000000 ? ts * 1000 : ts;
  const date = new Date(ms);
  if (isNaN(date.getTime())) return String(timestamp);
  return date.toLocaleString();
}

export function truncateHash(hash: string, start = 10, end = 8): string {
  if (!hash) return "N/A";
  if (hash.length <= start + end + 3) return hash;
  return `${hash.slice(0, start)}...${hash.slice(-end)}`;
}

export async function copyToClipboard(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KiB", "MiB", "GiB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}
