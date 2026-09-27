import { describe, expect, it } from "vitest";

import {
  profileSchema,
  profileUpdatePayload,
} from "@/features/auth/profile";

describe("profile form logic", () => {
  it("turns cleared optional fields into null", () => {
    const values = profileSchema.parse({
      first_name: "",
      last_name: "  ",
      phone_number: "",
      date_of_birth: "",
      gender: "",
    });

    expect(profileUpdatePayload(values)).toEqual({
      first_name: null,
      last_name: null,
      phone_number: null,
      date_of_birth: null,
      gender: null,
    });
  });

  it("respects backend field lengths", () => {
    expect(
      profileSchema.safeParse({
        first_name: "A",
        last_name: "Valid",
        phone_number: "123",
        date_of_birth: "2026-02-31",
        gender: "other",
      }).success,
    ).toBe(false);
  });

  it("creates a valid update payload", () => {
    const values = profileSchema.parse({
      first_name: "Amit",
      last_name: "Vishvakarma",
      phone_number: "1234567890",
      date_of_birth: "1990-01-02",
      gender: "male",
    });
    expect(profileUpdatePayload(values)).toMatchObject({
      first_name: "Amit",
      phone_number: "1234567890",
      date_of_birth: "1990-01-02",
      gender: "male",
    });
  });
});
