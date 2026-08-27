import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

// Suppress harmless ResizeObserver loop warnings that surface a full-page CRA
// dev-server overlay and block subsequent interactions. This is a well-known
// benign browser warning; see facebook/create-react-app#11889.
const RESIZE_OBSERVER_ERR = 'ResizeObserver loop';
window.addEventListener('error', (e) => {
  if (e?.message?.includes(RESIZE_OBSERVER_ERR)) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});
window.addEventListener('unhandledrejection', (e) => {
  if (String(e?.reason?.message || '').includes(RESIZE_OBSERVER_ERR)) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
