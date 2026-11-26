"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DeviceHint } from "@/components/ui/device-hint";
import { Input } from "@/components/ui/input";
import { SettingRow, SettingsSection } from "@/components/ui/setting-row";
import { Switch } from "@/components/ui/switch";
import { getApiKeyRepository } from "@/features/api-keys/repository";
import { useCurrentUser } from "@/features/auth/use-current-user";
import { getBackendHealth } from "@/features/health/api";
import { getIntegrationRepository } from "@/features/integrations/repository";
import {
  usePreferences,
  usePreferencesPersistence,
  useSavePreferences,
} from "@/features/preferences/queries";
import { useQuery } from "@tanstack/react-query";

export function NotificationsPage() {
  const prefs = usePreferences();
  const save = useSavePreferences();
  const persistence = usePreferencesPersistence();
  if (!prefs.data) return null;
  return (
    <SettingsSection
      title="Notifications"
      description="Alerts for this device until a notification API exists."
    >
      <SettingRow label="Product updates">
        <Switch
          checked={prefs.data.notifications.product}
          label="Product updates"
          onCheckedChange={(checked) =>
            void save.mutateAsync({
              ...prefs.data!,
              notifications: { ...prefs.data!.notifications, product: checked },
            })
          }
        />
      </SettingRow>
      <SettingRow label="Approval requests">
        <div className="space-y-1">
          <Switch
            checked={prefs.data.notifications.approvals}
            label="Approval requests"
            onCheckedChange={(checked) =>
              void save.mutateAsync({
                ...prefs.data!,
                notifications: {
                  ...prefs.data!.notifications,
                  approvals: checked,
                },
              })
            }
          />
          <DeviceHint persistence={persistence} />
        </div>
      </SettingRow>
    </SettingsSection>
  );
}

export function IntegrationsPage() {
  const user = useCurrentUser();
  const repo = user.data?.id ? getIntegrationRepository(user.data.id) : null;
  const list = useQuery({
    queryKey: ["integrations"],
    queryFn: () => repo!.list(),
    enabled: Boolean(repo),
  });
  return (
    <SettingsSection
      title="Integrations"
      description="MCP connectors. None are registered until the backend exposes them."
    >
      {list.data && list.data.length === 0 ? (
        <p className="py-6 text-sm text-muted-foreground">
          No connectors yet. Saved connectors will appear here.
        </p>
      ) : (
        (list.data ?? []).map((item) => (
          <SettingRow key={item.id} label={item.name} description={item.kind}>
            <Switch
              checked={item.enabled}
              label={`Enable ${item.name}`}
              onCheckedChange={(checked) =>
                repo && void repo.setEnabled(item.id, checked)
              }
            />
          </SettingRow>
        ))
      )}
      {repo ? <DeviceHint persistence={repo.persistence} /> : null}
    </SettingsSection>
  );
}

export function PermissionsPage() {
  return (
    <SettingsSection
      title="Permissions"
      description="Role assignments stay on the server. There is no capabilities API yet."
    >
      <p className="py-6 text-sm text-muted-foreground">
        You can view this page because the permissions flag is on. Managing
        roles requires a backend endpoint that is not shipped.
      </p>
    </SettingsSection>
  );
}

export function PrivacyPage() {
  return (
    <SettingsSection
      title="Data & privacy"
      description="Export and account deletion need dedicated API routes."
    >
      <SettingRow
        label="Export conversations"
        description="Download a copy of your chats when the export API exists."
      >
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => toast.error("Export is not available on the API yet.")}
        >
          Export
        </Button>
      </SettingRow>
      <SettingRow
        label="Delete conversations"
        description="Archive individual chats from the sidebar. Bulk delete is not available."
      >
        <Button type="button" variant="outline" size="sm" disabled>
          Unavailable
        </Button>
      </SettingRow>
    </SettingsSection>
  );
}

export function UsagePage() {
  const health = useQuery({
    queryKey: ["health", "backend"],
    queryFn: ({ signal }) => getBackendHealth(signal),
  });
  return (
    <SettingsSection
      title="Usage"
      description="Token and cost totals are not exposed by FastAPI. Service health is below."
    >
      <SettingRow label="API status">
        <p className="text-sm">
          {health.isPending
            ? "Loading…"
            : health.error
              ? "Unavailable"
              : health.data?.status}
        </p>
      </SettingRow>
      <SettingRow label="Tokens this period">
        <p className="text-sm text-muted-foreground">Not provided by the API</p>
      </SettingRow>
    </SettingsSection>
  );
}

export function ApiKeysPage() {
  const user = useCurrentUser();
  const repo = user.data?.id ? getApiKeyRepository(user.data.id) : null;
  const list = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => repo!.list(),
    enabled: Boolean(repo),
  });
  const [name, setName] = useState("");
  const [secret, setSecret] = useState<string | null>(null);

  return (
    <SettingsSection
      title="API keys"
      description="Device-local keys until FastAPI exposes a key registry. Copy a secret once."
    >
      <div className="flex gap-2 py-4">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Key name"
          aria-label="API key name"
        />
        <Button
          type="button"
          onClick={async () => {
            if (!repo) return;
            const created = await repo.create(name);
            setSecret(created.secret);
            setName("");
            void list.refetch();
          }}
        >
          Create
        </Button>
      </div>
      {secret ? (
        <p className="pb-3 text-sm">
          Secret (shown once): <code>{secret}</code>
        </p>
      ) : null}
      {(list.data ?? []).map((key) => (
        <SettingRow key={key.id} label={key.name} description={key.prefix}>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={async () => {
              await repo?.revoke(key.id);
              void list.refetch();
            }}
          >
            Revoke
          </Button>
        </SettingRow>
      ))}
      {repo ? <DeviceHint persistence={repo.persistence} /> : null}
    </SettingsSection>
  );
}

export function HelpPage() {
  return (
    <SettingsSection title="Help" description="Documentation and shortcuts.">
      <SettingRow label="Documentation">
        <p className="text-sm text-muted-foreground">clients/web/README.md</p>
      </SettingRow>
      <SettingRow
        label="Keyboard shortcuts"
        description="Press ? anywhere in the workspace."
      >
        <kbd className="rounded-md border border-border px-2 py-0.5 text-xs">?</kbd>
      </SettingRow>
    </SettingsSection>
  );
}

export function AdminPage() {
  return (
    <SettingsSection
      title="Admin"
      description="Visible only when NEXT_PUBLIC_FEATURE_ADMIN=true."
    >
      <p className="py-6 text-sm text-muted-foreground">
        No admin API is wired. This page is a placeholder for future operators
        tools.
      </p>
    </SettingsSection>
  );
}
