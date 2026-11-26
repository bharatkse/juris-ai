import { roleFlags } from "@/config/feature-backends";

export interface Capabilities {
  admin: boolean;
  permissions: boolean;
}

export function defaultCapabilities(): Capabilities {
  return {
    admin: roleFlags.admin,
    permissions: roleFlags.permissions,
  };
}
