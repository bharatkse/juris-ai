import type { LucideIcon } from "lucide-react";
import {
  BarChart3,
  Bell,
  BookOpen,
  Brain,
  CircleHelp,
  Folder,
  FolderInput,
  KeyRound,
  ListChecks,
  Lock,
  LogOut,
  Moon,
  Pencil,
  Pin,
  PinOff,
  Plug,
  Plus,
  Search,
  Settings,
  ShieldAlert,
  ShieldCheck,
  SquarePen,
  Sun,
  Trash2,
  User,
} from "lucide-react";

import type { Capabilities } from "@/features/auth/capabilities";

export const ICON_STROKE = 1.75;
export const ICON_SIZE = 18;

export const ICONS = {
  newChat: SquarePen,
  search: Search,
  library: BookOpen,
  projects: Folder,
  pinned: Pin,
  unpin: PinOff,
  plus: Plus,
  plans: ListChecks,
  profile: User,
  settings: Settings,
  memory: Brain,
  appearanceLight: Sun,
  appearanceDark: Moon,
  integrations: Plug,
  permissions: ShieldCheck,
  privacy: Lock,
  usage: BarChart3,
  apiKeys: KeyRound,
  notifications: Bell,
  help: CircleHelp,
  admin: ShieldAlert,
  signOut: LogOut,
  rename: Pencil,
  moveToProject: FolderInput,
  delete: Trash2,
} as const;

export type IconName = keyof typeof ICONS;

export function navIcon(name: IconName): LucideIcon {
  return ICONS[name];
}

export interface WorkNavItem {
  id: "new-chat" | "search" | "library" | "plans";
  label: string;
  icon: IconName;
  href?: string;
  action?: "new-chat" | "search";
  match: (pathname: string) => boolean;
}

export const WORK_NAV: readonly WorkNavItem[] = [
  {
    id: "new-chat",
    label: "New chat",
    icon: "newChat",
    action: "new-chat",
    match: () => false,
  },
  {
    id: "search",
    label: "Search",
    icon: "search",
    action: "search",
    match: () => false,
  },
  {
    id: "library",
    label: "Library",
    icon: "library",
    href: "/app/library",
    match: (pathname) =>
      pathname.startsWith("/app/library") ||
      pathname.startsWith("/app/documents"),
  },
  {
    id: "plans",
    label: "Plans",
    icon: "plans",
    href: "/app/approvals",
    match: (pathname) => pathname.startsWith("/app/approvals"),
  },
] as const;

export const SIDEBAR_SECTIONS = {
  pinned: { id: "pinned", label: "Pinned" },
  projects: { id: "projects", label: "Projects" },
  chats: { id: "chats-and-tasks", label: "Chats and tasks" },
} as const;

export interface SettingsNavItem {
  id:
    | "profile"
    | "general"
    | "memory"
    | "notifications"
    | "integrations"
    | "permissions"
    | "privacy"
    | "usage"
    | "api-keys";
  href: string;
  label: string;
  icon: IconName;
}

export const SETTINGS_NAV: readonly SettingsNavItem[] = [
  { id: "profile", href: "/settings/profile", label: "Profile", icon: "profile" },
  { id: "general", href: "/settings/general", label: "General", icon: "settings" },
  { id: "memory", href: "/settings/memory", label: "Memory", icon: "memory" },
  {
    id: "notifications",
    href: "/settings/notifications",
    label: "Notifications",
    icon: "notifications",
  },
  {
    id: "integrations",
    href: "/settings/integrations",
    label: "Integrations",
    icon: "integrations",
  },
  {
    id: "permissions",
    href: "/settings/permissions",
    label: "Permissions",
    icon: "permissions",
  },
  {
    id: "privacy",
    href: "/settings/privacy",
    label: "Data & privacy",
    icon: "privacy",
  },
  { id: "usage", href: "/settings/usage", label: "Usage", icon: "usage" },
  { id: "api-keys", href: "/settings/api-keys", label: "API keys", icon: "apiKeys" },
] as const;

export function visibleSettingsNav(
  capabilities: Capabilities,
): SettingsNavItem[] {
  return SETTINGS_NAV.filter((item) => {
    if (item.id === "permissions") return capabilities.permissions;
    return true;
  });
}

export function isSettingsPathActive(pathname: string, href: string): boolean {
  if (href === "/settings/memory") {
    return pathname === href || pathname.startsWith("/settings/memory/");
  }
  return pathname === href;
}

export type ProfileMenuAction =
  | {
      kind: "link";
      href: string;
      label: string;
      id: string;
      icon: IconName;
      group: "account" | "workspace" | "system";
    }
  | {
      kind: "appearance";
      id: "appearance";
      label: string;
      icon: IconName;
      group: "account";
    }
  | {
      kind: "signout";
      id: "signout";
      label: string;
      icon: IconName;
      group: "session";
    };

export function profileMenuItems(
  capabilities: Capabilities,
): ProfileMenuAction[] {
  const items: ProfileMenuAction[] = [
    {
      kind: "link",
      id: "profile",
      href: "/settings/profile",
      label: "Profile",
      icon: "profile",
      group: "account",
    },
    {
      kind: "link",
      id: "settings",
      href: "/settings/general",
      label: "Settings",
      icon: "settings",
      group: "account",
    },
    {
      kind: "link",
      id: "memory",
      href: "/settings/memory",
      label: "Memory",
      icon: "memory",
      group: "account",
    },
    {
      kind: "appearance",
      id: "appearance",
      label: "Appearance",
      icon: "appearanceLight",
      group: "account",
    },
    {
      kind: "link",
      id: "integrations",
      href: "/settings/integrations",
      label: "Integrations",
      icon: "integrations",
      group: "workspace",
    },
  ];
  if (capabilities.permissions) {
    items.push({
      kind: "link",
      id: "permissions",
      href: "/settings/permissions",
      label: "Permissions",
      icon: "permissions",
      group: "workspace",
    });
  }
  items.push({
    kind: "link",
    id: "help",
    href: "/settings/help",
    label: "Help",
    icon: "help",
    group: "system",
  });
  if (capabilities.admin) {
    items.push({
      kind: "link",
      id: "admin",
      href: "/settings/admin",
      label: "Admin",
      icon: "admin",
      group: "system",
    });
  }
  items.push({
    kind: "signout",
    id: "signout",
    label: "Sign out",
    icon: "signOut",
    group: "session",
  });
  return items;
}

export function allNavEntries(): Array<{ id: string; label: string; icon: IconName }> {
  return [
    ...WORK_NAV.map((item) => ({
      id: item.id,
      label: item.label,
      icon: item.icon,
    })),
    ...SETTINGS_NAV.map((item) => ({
      id: item.id,
      label: item.label,
      icon: item.icon,
    })),
  ];
}
