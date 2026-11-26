"use client";

import { toast } from "sonner";

import { DeviceHint } from "@/components/ui/device-hint";
import { SettingRow, SettingsSection } from "@/components/ui/setting-row";
import { Switch } from "@/components/ui/switch";
import {
  usePreferences,
  usePreferencesPersistence,
  useSavePreferences,
} from "@/features/preferences/queries";
import { useTheme } from "@/features/theme/provider";

export function GeneralPage() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const prefs = usePreferences();
  const save = useSavePreferences();
  const persistence = usePreferencesPersistence();
  const current =
    theme === "dark" || theme === "light"
      ? theme
      : resolvedTheme === "dark" || resolvedTheme === "light"
        ? resolvedTheme
        : "light";

  return (
    <SettingsSection
      title="General"
      description="Appearance and locale for this browser."
    >
      <SettingRow
        label="Appearance"
        description="Light uses a pure white canvas. Dark uses a soft charcoal surface."
      >
        <Switch
          checked={current === "dark"}
          label="Dark theme"
          onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
        />
      </SettingRow>
      <SettingRow label="Language" description="UI language for this device.">
        <div className="w-full space-y-1">
          <select
            className="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm"
            value={prefs.data?.language ?? "en"}
            onChange={(event) => {
              if (!prefs.data) return;
              void save
                .mutateAsync({ ...prefs.data, language: event.target.value })
                .then(() => toast.success("Language saved."));
            }}
            aria-label="Language"
          >
            <option value="en">English</option>
            <option value="hi">Hindi</option>
          </select>
          <DeviceHint persistence={persistence} />
        </div>
      </SettingRow>
      <SettingRow label="Time zone">
        <div className="w-full space-y-1">
          <select
            className="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm"
            value={prefs.data?.timezone ?? "Asia/Kolkata"}
            onChange={(event) => {
              if (!prefs.data) return;
              void save.mutateAsync({
                ...prefs.data,
                timezone: event.target.value,
              });
            }}
            aria-label="Time zone"
          >
            <option value="Asia/Kolkata">Asia/Kolkata</option>
            <option value="UTC">UTC</option>
            <option value="America/New_York">America/New_York</option>
          </select>
          <DeviceHint persistence={persistence} />
        </div>
      </SettingRow>
    </SettingsSection>
  );
}
