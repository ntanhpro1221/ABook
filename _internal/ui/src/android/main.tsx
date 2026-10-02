import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";
import { setApiTransport } from "@/studio/api";
import { initAndroidSource } from "./androidSource";
import { AndroidApp } from "./App";
import { localStudio } from "./localStudio";

// Sửa sách trên điện thoại: mọi `api()` đi vào lõi native (LocalStudio.kt), không có server để `fetch`.
setApiTransport(localStudio);

const client = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true, staleTime: 1000 } },
});

void initAndroidSource().finally(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <AndroidApp />
      </QueryClientProvider>
    </StrictMode>,
  );
});
