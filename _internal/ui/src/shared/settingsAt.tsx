// Bài thử: dựng màn Cài đặt ở một nhóm (`/settings/<nhóm>`) như Router của app - màn con là route thật (shared/SettingsNav.tsx).
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import type { SettingsGroupId } from "./SettingsNav";

export function SettingsAt({ group, screen }: { group?: SettingsGroupId; screen: ReactElement }) {
  return (
    <MemoryRouter initialEntries={[group ? `/settings/${group}` : "/settings"]}>
      <Routes>
        <Route path="/settings/:group?" element={screen} />
      </Routes>
    </MemoryRouter>
  );
}
