import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export function GET(): NextResponse {
  return NextResponse.json(
    { success: true, data: { status: "ok" } },
    { headers: { "Cache-Control": "no-store" } },
  );
}
