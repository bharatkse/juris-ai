import { describe, expect, it } from "vitest";

import { userIdFromAccessToken } from "@/lib/server/jwt";

function unsignedJwt(payload: object): string {
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `hdr.${body}.sig`;
}

describe("userIdFromAccessToken", () => {
  it("reads sub from a JWT payload", () => {
    expect(userIdFromAccessToken(unsignedJwt({ sub: "user_9" }))).toBe("user_9");
  });

  it("returns null for garbage", () => {
    expect(userIdFromAccessToken("not-a-jwt")).toBeNull();
  });
});
