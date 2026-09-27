import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().trim().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

const optionalName = z
  .string()
  .trim()
  .max(100, "Use 100 characters or fewer.")
  .refine(
    (value) => value.length === 0 || value.length >= 2,
    "Use at least 2 characters.",
  )
  .optional();

export const registerSchema = z
  .object({
    first_name: optionalName,
    last_name: optionalName,
    email: z.string().trim().email("Enter a valid email address."),
    password: z
      .string()
      .min(8, "Use at least 8 characters.")
      .max(128, "Use 128 characters or fewer."),
    confirm_password: z.string().min(1, "Confirm your password."),
  })
  .refine((values) => values.password === values.confirm_password, {
    message: "Passwords do not match.",
    path: ["confirm_password"],
  });

export type LoginValues = z.infer<typeof loginSchema>;
export type RegisterValues = z.infer<typeof registerSchema>;
