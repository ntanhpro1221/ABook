import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./desktop/App";
import { installDetailsMotion } from "./shared/motion";
import { createAppQueryClient } from "./shared/queryClient";
import "./styles.css";

const client = createAppQueryClient();
// Mọi <details> mở / gập có chuyển động (shared/motion.ts).
installDetailsMotion();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
